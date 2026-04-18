from __future__ import annotations

try:
    from scripts.clean_data import clean_data
    from scripts.features import create_features
    from scripts.fetch_data import fetch_and_store_live_snapshot
    from scripts.pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        CURRENT_RAW_HISTORY_PATH,
        SEED_HISTORY_PATH,
        build_archive_path,
        copy_file,
        prune_old_archives,
    )
    from scripts.train_model import train_model
except ModuleNotFoundError:
    from clean_data import clean_data
    from features import create_features
    from fetch_data import fetch_and_store_live_snapshot
    from pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_FEATURED_PATH,
        CURRENT_MODEL_PATH,
        CURRENT_RAW_HISTORY_PATH,
        SEED_HISTORY_PATH,
        build_archive_path,
        copy_file,
        prune_old_archives,
    )
    from train_model import train_model


def run_full_pipeline() -> dict[str, object]:
    print("Running full PSX pipeline...")

    fetch_result = fetch_and_store_live_snapshot()

    cleaned_dataframe = clean_data(
        fetch_result["latest_path"],
        CURRENT_CLEANED_PATH,
        history_path=SEED_HISTORY_PATH,
        merged_output_path=CURRENT_RAW_HISTORY_PATH,
    )
    if cleaned_dataframe is None:
        raise RuntimeError("Cleaning step failed.")

    raw_history_archive = build_archive_path("raw", "market_history", ".csv")
    copy_file(CURRENT_RAW_HISTORY_PATH, raw_history_archive)

    featured_dataframe = create_features(CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH)
    if featured_dataframe is None:
        raise RuntimeError("Feature engineering step failed.")

    cleaned_archive = build_archive_path("processed", "cleaned_data", ".csv")
    featured_archive = build_archive_path("processed", "featured_data", ".csv")
    copy_file(CURRENT_CLEANED_PATH, cleaned_archive)
    copy_file(CURRENT_FEATURED_PATH, featured_archive)

    model_bundle = train_model(CURRENT_FEATURED_PATH, CURRENT_MODEL_PATH)
    if model_bundle is None:
        raise RuntimeError("Training step failed.")

    model_archive = build_archive_path("models", "model", ".pkl")
    copy_file(CURRENT_MODEL_PATH, model_archive)

    deleted_files = {
        "raw": prune_old_archives("raw"),
        "processed": prune_old_archives("processed"),
        "models": prune_old_archives("models"),
    }

    summary = {
        "status": "success",
        "fetched_raw_archive": fetch_result["archive_path"],
        "latest_raw_file": fetch_result["latest_path"],
        "current_raw_history_file": str(CURRENT_RAW_HISTORY_PATH),
        "raw_history_archive": str(raw_history_archive),
        "current_cleaned_file": str(CURRENT_CLEANED_PATH),
        "cleaned_archive": str(cleaned_archive),
        "current_featured_file": str(CURRENT_FEATURED_PATH),
        "featured_archive": str(featured_archive),
        "current_model_file": str(CURRENT_MODEL_PATH),
        "model_archive": str(model_archive),
        "latest_prediction_date": model_bundle.get("latest_row_date"),
        "latest_features": model_bundle.get("latest_features"),
        "metrics": model_bundle.get("metrics"),
        "deleted_old_files": deleted_files,
    }

    print("Pipeline completed successfully.")
    return summary


if __name__ == "__main__":
    try:
        pipeline_summary = run_full_pipeline()
        print(pipeline_summary)
    except Exception as error:
        print(f"Pipeline failed: {error}")
