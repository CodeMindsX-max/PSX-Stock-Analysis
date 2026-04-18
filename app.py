from __future__ import annotations

import os
import pickle
import threading

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from scripts.pipeline_utils import (
    BASE_DIR,
    CURRENT_FEATURED_PATH,
    CURRENT_MODEL_PATH,
    delete_managed_file,
    list_managed_files,
    preview_managed_file,
)
from scripts.run_pipeline import run_full_pipeline


app = Flask(__name__)
PIPELINE_LOCK = threading.Lock()


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


def load_model_bundle():
    if not CURRENT_MODEL_PATH.exists():
        return None, "Model file not found. Run the pipeline first."

    try:
        with open(CURRENT_MODEL_PATH, "rb") as model_file:
            model_bundle = pickle.load(model_file)
    except Exception as error:
        return None, f"Could not load model file: {error}"

    if "model" not in model_bundle:
        return None, "Saved model bundle is missing the trained model."

    feature_columns = model_bundle.get("feature_columns")
    if feature_columns is None:
        feature_columns = model_bundle.get("features")

    if not feature_columns:
        return None, "Saved model bundle is missing feature column metadata."

    model_bundle["feature_columns"] = list(feature_columns)
    return model_bundle, None


def load_featured_data():
    if not CURRENT_FEATURED_PATH.exists():
        return None, "Processed feature data not found. Run the pipeline first."

    try:
        dataframe = pd.read_csv(CURRENT_FEATURED_PATH)
    except Exception as error:
        return None, f"Could not load processed data: {error}"

    if "Date" in dataframe.columns:
        dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")

    return dataframe, None


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


@app.route("/")
@app.route("/dashboard")
def dashboard():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@app.route("/health")
@app.route("/api/health")
def health():
    model_bundle, model_error = load_model_bundle()
    _, data_error = load_featured_data()

    return jsonify({
        "message": "PSX AI API is running",
        "model_ready": model_error is None,
        "data_ready": data_error is None,
        "model_error": model_error,
        "data_error": data_error,
        "pipeline_busy": PIPELINE_LOCK.locked(),
        "warnings": [] if model_error else (model_bundle.get("warnings") or []),
    })


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
    except Exception as error:
        return jsonify({"error": f"Prediction failed: {error}"}), 500

    result = "UP" if prediction == 1 else "DOWN"

    return jsonify({
        "prediction": result,
        "prediction_value": prediction,
        "latest_row_date": model_bundle.get("latest_row_date"),
        "feature_columns": model_bundle["feature_columns"],
        "latest_features": model_bundle.get("latest_features"),
        "warnings": model_bundle.get("warnings") or [],
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
        "average_return": normalize_value(dataframe["Return"].mean()),
        "average_volatility": normalize_value(dataframe["Volatility"].mean()),
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
        return jsonify({"error": f"Could not delete file: {error}"}), 500


@app.route("/api/pipeline/run", methods=["POST"])
def api_run_pipeline():
    if not PIPELINE_LOCK.acquire(blocking=False):
        return jsonify({"error": "Pipeline is already running."}), 409

    try:
        summary = run_full_pipeline()
        return jsonify(summary)
    except Exception as error:
        return jsonify({"error": f"Pipeline failed: {error}"}), 500
    finally:
        PIPELINE_LOCK.release()


if __name__ == "__main__":
    # app.run(debug=True)
    app.run()
