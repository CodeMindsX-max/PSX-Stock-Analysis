from __future__ import annotations

import logging
import pickle

import pandas as pd

try:
    from scripts.clean_data import clean_data
    from scripts.features import FEATURE_COLUMNS, create_features
    from scripts.fetch_data import fetch_and_store_live_snapshot
    from scripts.pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        CURRENT_RAW_HISTORY_PATH,
        SEED_HISTORY_PATH,
        build_archive_path,
        copy_file,
        ensure_current_history_file,
        ensure_seed_history_file,
        prune_old_archives,
    )
    from scripts.train_model import train_model
except ModuleNotFoundError:
    from clean_data import clean_data
    from features import FEATURE_COLUMNS, create_features
    from fetch_data import fetch_and_store_live_snapshot
    from pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        CURRENT_RAW_HISTORY_PATH,
        SEED_HISTORY_PATH,
        build_archive_path,
        copy_file,
        ensure_current_history_file,
        ensure_seed_history_file,
        prune_old_archives,
    )
    from train_model import train_model


LOGGER = logging.getLogger(__name__)


def featured_artifact_is_current() -> bool:
    if not CURRENT_FEATURED_PATH.exists():
        return False

    try:
        dataframe = pd.read_csv(CURRENT_FEATURED_PATH, nrows=1)
    except Exception:
        return False

    required_columns = set(FEATURE_COLUMNS) | {"Target", "Date"}
    return required_columns.issubset(dataframe.columns)


def model_artifact_is_current() -> bool:
    if not CURRENT_MODEL_PATH.exists():
        return False

    try:
        with open(CURRENT_MODEL_PATH, "rb") as model_file:
            bundle = pickle.load(model_file)
    except Exception:
        return False

    if not isinstance(bundle, dict):
        return False

    bundle_columns = list(bundle.get("feature_columns") or [])
    return (
        bundle.get("model_version") is not None
        and bundle.get("latest_prediction_probabilities") is not None
        and bundle_columns == list(FEATURE_COLUMNS)
    )


def bootstrap_local_artifacts() -> dict[str, object]:
    history_source = ensure_current_history_file()
    ensure_seed_history_file()

    summary: dict[str, object] = {
        "history_source": str(history_source),
        "rebuilt_cleaned": False,
        "rebuilt_featured": False,
        "rebuilt_model": False,
    }

    if not CURRENT_CLEANED_PATH.exists():
        clean_data(history_source, CURRENT_CLEANED_PATH, merged_output_path=CURRENT_RAW_HISTORY_PATH)
        summary["rebuilt_cleaned"] = True

    if not featured_artifact_is_current():
        create_features(CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH)
        summary["rebuilt_featured"] = True

    if not model_artifact_is_current():
        train_model(CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH)
        summary["rebuilt_model"] = True

    return summary


def run_full_pipeline() -> dict[str, object]:
    LOGGER.info("Running full PSX pipeline.")
    history_source = ensure_current_history_file()
    ensure_seed_history_file()

    fetch_result = fetch_and_store_live_snapshot()
    LOGGER.info("Live snapshot saved to %s", fetch_result["latest_path"])

    cleaned_dataframe = clean_data(
        fetch_result["latest_path"],
        CURRENT_CLEANED_PATH,
        history_path=history_source,
        merged_output_path=CURRENT_RAW_HISTORY_PATH,
    )

    raw_history_archive = build_archive_path("raw", "market_history", ".csv")
    copy_file(CURRENT_RAW_HISTORY_PATH, raw_history_archive)

    featured_dataframe = create_features(CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH)
    cleaned_archive = build_archive_path("processed", "cleaned_data", ".csv")
    featured_archive = build_archive_path("processed", "featured_data", ".csv")
    copy_file(CURRENT_CLEANED_PATH, cleaned_archive)
    copy_file(CURRENT_FEATURED_PATH, featured_archive)

    model_bundle = train_model(CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH)
    deleted_files = {
        "raw": prune_old_archives("raw"),
        "processed": prune_old_archives("processed"),
        "models": prune_old_archives("models"),
    }

    summary = {
        "status": "success",
        "seed_history_file": str(SEED_HISTORY_PATH),
        "history_source_used": str(history_source),
        "fetched_raw_archive": fetch_result["archive_path"],
        "latest_raw_file": fetch_result["latest_path"],
        "current_raw_history_file": str(CURRENT_RAW_HISTORY_PATH),
        "raw_history_archive": str(raw_history_archive),
        "current_cleaned_file": str(CURRENT_CLEANED_PATH),
        "cleaned_archive": str(cleaned_archive),
        "current_featured_file": str(CURRENT_FEATURED_PATH),
        "featured_archive": str(featured_archive),
        "current_model_file": str(CURRENT_MODEL_PATH),
        "versioned_model_file": model_bundle.get("versioned_model_path"),
        "model_registry_file": model_bundle.get("model_registry_path"),
        "latest_prediction_date": model_bundle.get("latest_row_date"),
        "latest_features": model_bundle.get("latest_features"),
        "metrics": model_bundle.get("metrics"),
        "cleaned_rows": len(cleaned_dataframe),
        "featured_rows": len(featured_dataframe),
        "deleted_old_files": deleted_files,
    }

    LOGGER.info("Pipeline completed successfully.")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        pipeline_summary = run_full_pipeline()
        LOGGER.info("Pipeline summary: %s", pipeline_summary)
    except Exception as error:
        LOGGER.exception("Pipeline failed: %s", error)
