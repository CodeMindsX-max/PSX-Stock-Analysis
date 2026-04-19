from __future__ import annotations

from pathlib import Path
import pickle

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import TimeSeriesSplit

try:
    from scripts.features import FEATURE_COLUMNS
    from scripts.pipeline_utils import (
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        MODEL_REGISTRY_PATH,
        append_model_registry_entry,
        build_archive_path,
        copy_file,
        timestamp_slug,
    )
except ModuleNotFoundError:
    from features import FEATURE_COLUMNS
    from pipeline_utils import (
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        MODEL_REGISTRY_PATH,
        append_model_registry_entry,
        build_archive_path,
        copy_file,
        timestamp_slug,
    )


TARGET_COLUMN = "Target"
REQUIRED_COLUMNS = ["Date", *FEATURE_COLUMNS, TARGET_COLUMN]


def build_classifier() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
    )


def compute_metric_summary(y_true: pd.Series, y_pred: pd.Series) -> dict[str, object]:
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1_score, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="binary",
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1_score),
        "support": int(len(y_true)),
        "confusion_matrix": matrix,
    }


def evaluate_walk_forward(training_df: pd.DataFrame) -> list[dict[str, object]]:
    fold_count = min(5, max(2, len(training_df) // 30))
    if len(training_df) < 24 or fold_count < 2:
        return []

    splitter = TimeSeriesSplit(n_splits=fold_count)
    evaluations: list[dict[str, object]] = []

    for fold_number, (train_index, test_index) in enumerate(splitter.split(training_df), start=1):
        train_fold = training_df.iloc[train_index]
        test_fold = training_df.iloc[test_index]
        if train_fold.empty or test_fold.empty:
            continue
        if train_fold[TARGET_COLUMN].nunique() < 2 or test_fold[TARGET_COLUMN].nunique() < 2:
            continue

        model = build_classifier()
        model.fit(train_fold[list(FEATURE_COLUMNS)], train_fold[TARGET_COLUMN])
        predictions = model.predict(test_fold[list(FEATURE_COLUMNS)])
        summary = compute_metric_summary(test_fold[TARGET_COLUMN], predictions)
        summary["fold"] = fold_number
        summary["train_rows"] = int(len(train_fold))
        summary["test_rows"] = int(len(test_fold))
        evaluations.append(summary)

    return evaluations


def train_model(input_path: str | Path, model_path: str | Path) -> dict[str, object]:
    input_path = Path(input_path)
    model_path = Path(model_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    dataframe = pd.read_csv(input_path)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {input_path.name}: {', '.join(missing_columns)}")

    dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")
    for column in FEATURE_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
    dataframe[TARGET_COLUMN] = pd.to_numeric(dataframe[TARGET_COLUMN], errors="coerce")

    dataframe = dataframe.drop_duplicates(subset=["Date"], keep="last")
    dataframe = dataframe.sort_values(by="Date").reset_index(drop=True)

    latest_row_df = dataframe.dropna(subset=list(FEATURE_COLUMNS)).tail(1)
    if latest_row_df.empty:
        raise ValueError("No complete latest row is available for Flask/API use.")

    latest_row = latest_row_df.iloc[0]
    latest_features = {feature: float(latest_row[feature]) for feature in FEATURE_COLUMNS}
    latest_date = latest_row["Date"].strftime("%Y-%m-%d")
    warnings: list[str] = []

    dated_rows = dataframe["Date"].dropna()
    latest_gap_days = None
    if len(dated_rows) >= 2:
        latest_gap_days = int((dated_rows.iloc[-1] - dated_rows.iloc[-2]).days)
        if latest_gap_days > 10:
            warnings.append(
                f"Latest data gap is {latest_gap_days} days. Refresh the historical baseline for more reliable live features."
            )

    training_df = dataframe.dropna(subset=list(FEATURE_COLUMNS) + [TARGET_COLUMN]).copy()
    if training_df.empty:
        raise ValueError("No valid rows are available for model training.")

    training_df[TARGET_COLUMN] = training_df[TARGET_COLUMN].astype(int)
    if training_df[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Target column needs at least two classes for training.")

    train_size = int(len(training_df) * 0.8)
    if train_size == 0 or train_size == len(training_df):
        raise ValueError("Not enough rows were available to create both training and testing sets.")

    train_df = training_df.iloc[:train_size]
    test_df = training_df.iloc[train_size:]
    if train_df.empty or test_df.empty:
        raise ValueError("Training or testing split is empty.")
    if train_df[TARGET_COLUMN].nunique() < 2 or test_df[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Training and testing splits must each contain both target classes.")

    holdout_model = build_classifier()
    holdout_model.fit(train_df[list(FEATURE_COLUMNS)], train_df[TARGET_COLUMN])
    test_predictions = holdout_model.predict(test_df[list(FEATURE_COLUMNS)])
    holdout_probabilities = holdout_model.predict_proba(test_df[list(FEATURE_COLUMNS)])

    holdout_metrics = compute_metric_summary(test_df[TARGET_COLUMN], test_predictions)
    holdout_metrics["train_rows"] = int(len(train_df))
    holdout_metrics["test_rows"] = int(len(test_df))
    holdout_metrics["average_positive_probability"] = float(holdout_probabilities[:, 1].mean())

    walk_forward_metrics = evaluate_walk_forward(training_df)
    averaged_walk_forward_metrics = {}
    if walk_forward_metrics:
        averaged_walk_forward_metrics = {
            metric_name: round(
                sum(float(fold[metric_name]) for fold in walk_forward_metrics) / len(walk_forward_metrics),
                6,
            )
            for metric_name in ("accuracy", "precision", "recall", "f1")
        }

    final_model = build_classifier()
    final_model.fit(training_df[list(FEATURE_COLUMNS)], training_df[TARGET_COLUMN])
    latest_input = pd.DataFrame([latest_features])
    latest_probabilities = final_model.predict_proba(latest_input)[0]

    model_version = timestamp_slug()
    versioned_model_path = build_archive_path("models", "model", ".pkl", stamp=model_version)

    model_bundle = {
        "model": final_model,
        "model_version": model_version,
        "feature_columns": list(FEATURE_COLUMNS),
        "target_column": TARGET_COLUMN,
        "latest_row_date": latest_date,
        "latest_features": latest_features,
        "latest_prediction_probabilities": {
            "down": float(latest_probabilities[0]),
            "up": float(latest_probabilities[1]),
        },
        "training_completed": True,
        "metrics": {
            "holdout": holdout_metrics,
            "walk_forward_average": averaged_walk_forward_metrics,
            "walk_forward_folds": walk_forward_metrics,
        },
        "data_profile": {
            "total_rows": int(len(dataframe)),
            "training_rows": int(len(training_df)),
            "feature_count": len(FEATURE_COLUMNS),
            "latest_gap_days": latest_gap_days,
        },
        "warnings": warnings,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(versioned_model_path, "wb") as model_file:
        pickle.dump(model_bundle, model_file)

    copy_file(versioned_model_path, model_path)
    model_bundle["saved_model_path"] = str(model_path)
    model_bundle["versioned_model_path"] = str(versioned_model_path)

    append_model_registry_entry({
        "model_version": model_version,
        "saved_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "current_model_path": str(model_path),
        "versioned_model_path": str(versioned_model_path),
        "featured_input_path": str(input_path),
        "feature_columns": list(FEATURE_COLUMNS),
        "metrics": model_bundle["metrics"],
        "data_profile": model_bundle["data_profile"],
        "warnings": warnings,
    })
    model_bundle["model_registry_path"] = str(MODEL_REGISTRY_PATH)
    return model_bundle


if __name__ == "__main__":
    train_model(CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH)
