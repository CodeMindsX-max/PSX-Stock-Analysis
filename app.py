from __future__ import annotations

import functools
import logging
import os
import pickle
import threading

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from scripts.pipeline_utils import (
    BASE_DIR,
    CURRENT_FEATURED_PATH,
    delete_managed_file,
    list_managed_files,
    preview_managed_file,
    resolve_active_model_path,
)
from scripts.run_pipeline import bootstrap_local_artifacts, run_full_pipeline


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
RUNNING_ON_VERCEL = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))
PIPELINE_LOCK = threading.Lock()
CACHE_LOCK = threading.Lock()
PIPELINE_STATE_LOCK = threading.Lock()

MODEL_CACHE: dict[str, object] = {"path": None, "mtime": None, "bundle": None, "error": None}
DATA_CACHE: dict[str, object] = {"path": CURRENT_FEATURED_PATH, "mtime": None, "dataframe": None, "error": None}
PIPELINE_STATE: dict[str, object] = {
    "status": "idle",
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_error": None,
    "last_summary": None,
}


def normalize_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    return value


def dataframe_to_records(dataframe):
    records = []

    for _, row in dataframe.iterrows():
        record = {}
        for column, value in row.items():
            record[column] = normalize_value(value)
        records.append(record)

    return records


def get_pipeline_state() -> dict[str, object]:
    with PIPELINE_STATE_LOCK:
        return dict(PIPELINE_STATE)


def update_pipeline_state(**updates) -> dict[str, object]:
    with PIPELINE_STATE_LOCK:
        PIPELINE_STATE.update(updates)
        return dict(PIPELINE_STATE)


def pipeline_execution_supported() -> bool:
    return not RUNNING_ON_VERCEL


def should_bootstrap_runtime_state() -> bool:
    if not RUNNING_ON_VERCEL:
        return True
    return os.getenv("PSX_ENABLE_VERCEL_BOOTSTRAP", "").strip() == "1"


def load_model_bundle(force_reload: bool = False):
    model_path = resolve_active_model_path()
    if not model_path.exists():
        if RUNNING_ON_VERCEL:
            return None, (
                "Model file not found in this Vercel deployment. "
                "Deploy models/model.pkl with the repo or use external persistent storage."
            )
        return None, "Model file not found. Run the pipeline first."

    try:
        modified_time = model_path.stat().st_mtime
    except OSError as error:
        return None, f"Could not read model metadata: {error}"

    with CACHE_LOCK:
        cached_bundle = MODEL_CACHE.get("bundle")
        if (
            not force_reload
            and cached_bundle is not None
            and MODEL_CACHE.get("path") == str(model_path)
            and MODEL_CACHE.get("mtime") == modified_time
        ):
            return cached_bundle, MODEL_CACHE.get("error")

        try:
            with open(model_path, "rb") as model_file:
                model_bundle = pickle.load(model_file)
        except Exception as error:
            MODEL_CACHE.update({
                "path": str(model_path),
                "mtime": modified_time,
                "bundle": None,
                "error": f"Could not load model file: {error}",
            })
            return None, MODEL_CACHE["error"]

        if "model" not in model_bundle:
            MODEL_CACHE.update({
                "path": str(model_path),
                "mtime": modified_time,
                "bundle": None,
                "error": "Saved model bundle is missing the trained model.",
            })
            return None, MODEL_CACHE["error"]

        feature_columns = model_bundle.get("feature_columns") or model_bundle.get("features")
        if not feature_columns:
            MODEL_CACHE.update({
                "path": str(model_path),
                "mtime": modified_time,
                "bundle": None,
                "error": "Saved model bundle is missing feature column metadata.",
            })
            return None, MODEL_CACHE["error"]

        model_bundle["feature_columns"] = list(feature_columns)
        MODEL_CACHE.update({
            "path": str(model_path),
            "mtime": modified_time,
            "bundle": model_bundle,
            "error": None,
        })
        return model_bundle, None


def load_featured_data(force_reload: bool = False):
    if not CURRENT_FEATURED_PATH.exists():
        return None, "Processed feature data not found. Run the pipeline first."

    try:
        modified_time = CURRENT_FEATURED_PATH.stat().st_mtime
    except OSError as error:
        return None, f"Could not read processed data metadata: {error}"

    with CACHE_LOCK:
        cached_frame = DATA_CACHE.get("dataframe")
        if (
            not force_reload
            and cached_frame is not None
            and DATA_CACHE.get("mtime") == modified_time
        ):
            return cached_frame, DATA_CACHE.get("error")

        try:
            dataframe = pd.read_csv(CURRENT_FEATURED_PATH)
        except Exception as error:
            DATA_CACHE.update({
                "mtime": modified_time,
                "dataframe": None,
                "error": f"Could not load processed data: {error}",
            })
            return None, DATA_CACHE["error"]

        if "Date" in dataframe.columns:
            dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")

        DATA_CACHE.update({
            "mtime": modified_time,
            "dataframe": dataframe,
            "error": None,
        })
        return dataframe, None


def refresh_runtime_cache(force_reload: bool = True) -> None:
    load_featured_data(force_reload=force_reload)
    load_model_bundle(force_reload=force_reload)


def build_latest_input(model_bundle):
    feature_columns = model_bundle["feature_columns"]
    latest_features = model_bundle.get("latest_features")

    if latest_features:
        missing_features = [feature for feature in feature_columns if feature not in latest_features]
        if missing_features:
            return None, f"Latest feature snapshot is missing columns: {', '.join(missing_features)}"

        feature_row = {}
        for feature in feature_columns:
            value = latest_features.get(feature)
            if value is None or pd.isna(value):
                return None, f"Latest feature snapshot contains missing value for: {feature}"
            feature_row[feature] = value

        return pd.DataFrame([feature_row]), None

    dataframe, data_error = load_featured_data()
    if data_error:
        return None, data_error

    missing_features = [feature for feature in feature_columns if feature not in dataframe.columns]
    if missing_features:
        return None, f"Processed data is missing feature columns: {', '.join(missing_features)}"

    latest_row = dataframe.dropna(subset=feature_columns).tail(1)
    if latest_row.empty:
        return None, "No complete latest row is available for prediction."

    return latest_row[feature_columns], None


def run_pipeline_background_job() -> None:
    update_pipeline_state(
        status="running",
        running=True,
        started_at=pd.Timestamp.now(tz="UTC").isoformat(),
        finished_at=None,
        last_error=None,
    )
    LOGGER.info("Background pipeline execution started.")

    try:
        summary = run_full_pipeline()
        refresh_runtime_cache(force_reload=True)
        update_pipeline_state(
            status="completed",
            running=False,
            finished_at=pd.Timestamp.now(tz="UTC").isoformat(),
            last_summary=summary,
        )
        LOGGER.info("Background pipeline execution completed successfully.")
    except Exception as error:
        update_pipeline_state(
            status="failed",
            running=False,
            finished_at=pd.Timestamp.now(tz="UTC").isoformat(),
            last_error=str(error),
        )
        LOGGER.exception("Background pipeline execution failed: %s", error)
    finally:
        PIPELINE_LOCK.release()


def start_pipeline_job():
    if not pipeline_execution_supported():
        return False

    if not PIPELINE_LOCK.acquire(blocking=False):
        return False

    thread = threading.Thread(target=run_pipeline_background_job, daemon=True)
    thread.start()
    return True


def bootstrap_runtime_state() -> None:
    try:
        if should_bootstrap_runtime_state():
            summary = bootstrap_local_artifacts()
            if any(summary.values()):
                LOGGER.info("Bootstrap summary: %s", summary)
        else:
            LOGGER.info("Skipping heavy bootstrap on Vercel import.")

        refresh_runtime_cache(force_reload=True)
    except Exception as error:
        LOGGER.warning("Runtime bootstrap could not finish: %s", error)


@app.route("/")
@app.route("/dashboard")
def dashboard():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@app.route("/health")
@app.route("/api/health")
def health():
    model_bundle, model_error = load_model_bundle()
    _, data_error = load_featured_data()
    pipeline_state = get_pipeline_state()

    return jsonify({
        "message": "PSX AI API is running",
        "deployment_target": "vercel" if RUNNING_ON_VERCEL else "standard",
        "model_ready": model_error is None,
        "data_ready": data_error is None,
        "model_error": model_error,
        "data_error": data_error,
        "pipeline_busy": pipeline_state["running"],
        "pipeline_supported": pipeline_execution_supported(),
        "pipeline_status": pipeline_state["status"],
        "pipeline_started_at": pipeline_state["started_at"],
        "pipeline_finished_at": pipeline_state["finished_at"],
        "pipeline_error": pipeline_state["last_error"],
        "warnings": [] if model_error else (model_bundle.get("warnings") or []),
    })


@app.route("/api/pipeline/status", methods=["GET"])
def api_pipeline_status():
    return jsonify(get_pipeline_state())


@app.route("/data", methods=["GET"])
@app.route("/api/data", methods=["GET"])
def get_data():
    dataframe, data_error = load_featured_data()
    if data_error:
        return jsonify({"error": data_error}), 404

    latest_data = dataframe.tail(10)
    return jsonify(dataframe_to_records(latest_data))


@app.route("/predict", methods=["GET"])
@app.route("/api/predict", methods=["GET"])
def predict():
    model_bundle, model_error = load_model_bundle()
    if model_error:
        return jsonify({"error": model_error}), 404

    latest_input, input_error = build_latest_input(model_bundle)
    if input_error:
        return jsonify({"error": input_error}), 400

    try:
        prediction = int(model_bundle["model"].predict(latest_input)[0])
        probabilities = model_bundle["model"].predict_proba(latest_input)[0]
    except Exception as error:
        LOGGER.exception("Prediction failed: %s", error)
        return jsonify({"error": f"Prediction failed: {error}"}), 500

    result = "UP" if prediction == 1 else "DOWN"

    return jsonify({
        "prediction": result,
        "prediction_value": prediction,
        "prediction_probability_down": float(probabilities[0]),
        "prediction_probability_up": float(probabilities[1]),
        "confidence": float(max(probabilities)),
        "model_version": model_bundle.get("model_version"),
        "latest_row_date": model_bundle.get("latest_row_date"),
        "feature_columns": model_bundle["feature_columns"],
        "latest_features": model_bundle.get("latest_features"),
        "warnings": model_bundle.get("warnings") or [],
        "metrics": model_bundle.get("metrics") or {},
    })


@app.route("/insights", methods=["GET"])
@app.route("/api/insights", methods=["GET"])
def insights():
    dataframe, data_error = load_featured_data()
    if data_error:
        return jsonify({"error": data_error}), 404

    required_columns = ["Return", "Volatility"]
    missing_columns = [column for column in required_columns if column not in dataframe.columns]
    if missing_columns:
        return jsonify({
            "error": f"Processed data is missing insight columns: {', '.join(missing_columns)}"
        }), 400

    insights_payload = {
        "average_return": normalize_value(dataframe["Return"].dropna().mean()),
        "average_volatility": normalize_value(dataframe["Volatility"].dropna().mean()),
    }

    return jsonify(insights_payload)


@app.route("/api/files", methods=["GET"])
def api_files():
    return jsonify(list_managed_files())


@app.route("/api/files/preview", methods=["GET"])
def api_file_preview():
    category = request.args.get("category", "").strip()
    filename = request.args.get("filename", "").strip()

    if not category or not filename:
        return jsonify({"error": "Both category and filename are required."}), 400

    try:
        return jsonify(preview_managed_file(category, filename))
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        LOGGER.exception("Could not preview managed file: %s", error)
        return jsonify({"error": f"Could not preview file: {error}"}), 500


@app.route("/api/files/delete", methods=["POST"])
def api_delete_file():
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category", "")).strip()
    filename = str(payload.get("filename", "")).strip()

    if not category or not filename:
        return jsonify({"error": "Both category and filename are required."}), 400

    try:
        deleted = delete_managed_file(category, filename)
        LOGGER.info("Deleted managed file %s/%s", category, filename)
        return jsonify({
            "message": "File deleted successfully.",
            "deleted": deleted,
            "files": list_managed_files(),
        })
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        LOGGER.exception("Could not delete managed file: %s", error)
        return jsonify({"error": f"Could not delete file: {error}"}), 500


@app.route("/api/pipeline/run", methods=["POST"])
def api_run_pipeline():
    if not pipeline_execution_supported():
        return jsonify({
            "error": "Pipeline execution is disabled on Vercel serverless deployments.",
            "detail": "Run the training pipeline locally or on a dedicated worker environment, then deploy the generated artifacts.",
        }), 501

    if not start_pipeline_job():
        return jsonify({"error": "Pipeline is already running.", "status": get_pipeline_state()}), 409

    return jsonify({
        "message": "Pipeline started in the background.",
        "status": get_pipeline_state(),
    }), 202


bootstrap_runtime_state()


if __name__ == "__main__":
    app.run()
