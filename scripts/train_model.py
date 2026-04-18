from __future__ import annotations

from pathlib import Path
import pickle

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

try:
    from scripts.pipeline_utils import CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH
except ModuleNotFoundError:
    from pipeline_utils import CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH


FEATURE_COLUMNS = ("High", "Low", "Close", "Volume", "Return", "MA_7", "MA_30", "Volatility")
TARGET_COLUMN = "Target"
REQUIRED_COLUMNS = ["Date", *FEATURE_COLUMNS, TARGET_COLUMN]


def train_model(input_path: str | Path, model_path: str | Path) -> dict[str, object] | None:
    try:
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

        invalid_feature_values = dataframe[list(FEATURE_COLUMNS)].isna().sum()
        invalid_feature_values = invalid_feature_values[invalid_feature_values > 0]
        if not invalid_feature_values.empty:
            print(f"Feature rows with missing values will be skipped: {invalid_feature_values.to_dict()}")

        dataframe = dataframe.drop_duplicates(subset=["Date"], keep="last")
        dataframe = dataframe.sort_values(by="Date").reset_index(drop=True)

        latest_row_df = dataframe.dropna(subset=list(FEATURE_COLUMNS)).tail(1)
        if latest_row_df.empty:
            raise ValueError("No complete latest row is available for Flask/API use.")

        latest_row = latest_row_df.iloc[0]
        latest_features = {feature: float(latest_row[feature]) for feature in FEATURE_COLUMNS}
        latest_date = latest_row["Date"].strftime("%Y-%m-%d")
        warnings: list[str] = []

        if len(dataframe) >= 2:
            previous_date = dataframe["Date"].dropna().iloc[-2]
            latest_date_value = dataframe["Date"].dropna().iloc[-1]
            latest_gap_days = int((latest_date_value - previous_date).days)
            if latest_gap_days > 10:
                warnings.append(
                    f"Latest data gap is {latest_gap_days} days. Refresh the historical baseline for more reliable live features."
                )
        else:
            latest_gap_days = None

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

        X_train = train_df[list(FEATURE_COLUMNS)]
        y_train = train_df[TARGET_COLUMN]
        X_test = test_df[list(FEATURE_COLUMNS)]
        y_test = test_df[TARGET_COLUMN]

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, zero_division=0)

        print("Accuracy:", accuracy)
        print("\nClassification Report:\n", report)
        print("Training completed successfully")

        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_data = {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "latest_row_date": latest_date,
            "latest_features": latest_features,
            "training_completed": True,
            "metrics": {
                "accuracy": accuracy,
                "train_rows": len(train_df),
                "test_rows": len(test_df),
            },
            "data_profile": {
                "total_rows": len(dataframe),
                "training_rows": len(training_df),
                "feature_count": len(FEATURE_COLUMNS),
                "latest_gap_days": latest_gap_days,
            },
            "warnings": warnings,
        }

        with open(model_path, "wb") as model_file:
            pickle.dump(model_data, model_file)

        print("Model saved to:", model_path)
        print("Latest feature row saved with model for Flask API use.")
        return model_data
    except Exception as error:
        print(f"Error while training model: {error}")
        return None


if __name__ == "__main__":
    train_model(CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH)
