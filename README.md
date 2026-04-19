# PSX Stock Analysis

This project is an end-to-end PSX market pipeline and dashboard. It fetches the latest PSX KSE-100 snapshot, merges it into cumulative history, cleans the dataset, builds machine learning features, trains a direction model, and serves both a Flask API and a responsive dashboard.

## Architecture

Data flow:

`PSX website -> scripts/fetch_data.py -> scripts/clean_data.py -> scripts/features.py -> scripts/train_model.py -> Flask API -> dashboard`

Main components:

- `scripts/fetch_data.py`: fetches and validates the latest PSX KSE-100 snapshot
- `scripts/clean_data.py`: merges live data into cumulative history and normalizes schema
- `scripts/features.py`: builds model features such as returns, moving averages, volatility, RSI, MACD, and calendar fields
- `scripts/train_model.py`: trains a RandomForest model, evaluates it, versions it, and updates a registry
- `scripts/run_pipeline.py`: bootstraps missing artifacts and runs the full pipeline
- `app.py`: serves the dashboard, prediction API, health endpoints, pipeline status, and protected admin routes
- `static/index.html`: responsive dashboard with charts, auto-refresh, admin-token flow, and managed file previews

## Setup

Requirements:

- Python 3.11+
- Internet access for live PSX fetching

Install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Supported environment variables:

- `PSX_ADMIN_TOKEN`: required for admin actions such as running the pipeline and browsing/deleting managed files
- `APP_DATA_DIR`: overrides the root data directory
- `APP_RAW_DIR`: overrides the raw-data directory
- `APP_PROCESSED_DIR`: overrides the processed-data directory
- `APP_MODELS_DIR`: overrides the models directory
- `APP_SEED_HISTORY_PATH`: overrides the base historical seed CSV path
- `APP_CURRENT_HISTORY_PATH`: overrides the active cumulative history CSV path
- `APP_CURRENT_CLEANED_PATH`: overrides the cleaned dataset path
- `APP_CURRENT_FEATURED_PATH`: overrides the featured dataset path
- `APP_CURRENT_MODEL_PATH`: overrides the active model alias path
- `APP_MODEL_REGISTRY_PATH`: overrides the model registry JSON path
- `APP_ARCHIVE_LIMIT`: number of archived files to keep per category

Example:

```powershell
$env:PSX_ADMIN_TOKEN = "replace-with-a-secret-token"
$env:APP_DATA_DIR = "D:\\persistent-storage\\psx-data"
```

## Directory Layout

- `app.py`: Flask entrypoint
- `static/`: dashboard assets
- `scripts/`: data pipeline and model training scripts
- `tests/`: unit tests
- `data/raw/`: seed data, live snapshots, and cumulative raw history
- `data/processed/`: cleaned and featured datasets
- `models/`: current model alias, versioned models, and model registry

## Running The App

Start the Flask app:

```bash
python app.py
```

Open:

- Dashboard: `http://127.0.0.1:5000/`
- Health: `http://127.0.0.1:5000/health`

On startup the app attempts to bootstrap missing local artifacts from available seed/history data, so a fresh environment can rebuild `cleaned_data.csv`, `featured_data.csv`, and `model.pkl` without fetching live data first.

## Running The Pipeline

Run the full pipeline directly:

```bash
python -m scripts.run_pipeline
```

What it does:

1. Fetches the latest PSX live snapshot
2. Merges it into cumulative history
3. Rebuilds cleaned and featured datasets
4. Retrains the model
5. Writes a versioned model file and updates `models/model_registry.json`
6. Prunes older archives

## API Routes

Public routes:

- `GET /health` or `GET /api/health`
- `GET /data` or `GET /api/data`
- `GET /predict` or `GET /api/predict`
- `GET /insights` or `GET /api/insights`
- `GET /api/pipeline/status`

Protected admin routes:

- `POST /api/pipeline/run`
- `GET /api/files`
- `GET /api/files/preview?category=...&filename=...`
- `POST /api/files/delete`

Protected routes require header:

```http
X-Admin-Token: your-secret-token
```

Example prediction request:

```bash
curl http://127.0.0.1:5000/predict
```

Example protected pipeline request:

```bash
curl -X POST http://127.0.0.1:5000/api/pipeline/run ^
  -H "Content-Type: application/json" ^
  -H "X-Admin-Token: your-secret-token"
```

## Dashboard Notes

- The dashboard is responsive across desktop and mobile layouts
- Admin actions are disabled until an admin token is configured on the server and entered in the UI
- Pipeline runs now execute in the background and the dashboard polls status until completion
- The snapshot panel matches actual backend features and no longer depends on a missing `Open` feature

## Deployment

The app includes a `Procfile` for Gunicorn:

```text
web: gunicorn app:app
```

Deployment checklist:

- Set `PSX_ADMIN_TOKEN`
- Mount persistent storage or point the `APP_*` paths to persistent directories
- Install from `requirements.txt`
- Ensure outbound internet access is available for live PSX fetches if scheduled retraining is needed

Suggested platforms:

- Railway
- Render
- Heroku-style platforms that support Gunicorn and persistent volumes

## Testing

Run tests with:

```bash
python -m unittest tests.test_psx_pipeline
```

## Current Limits

- The dashboard still references Tailwind and Chart.js via CDN; local vendoring was not added in this pass
- Live PSX scraping still depends on the upstream site structure, though parsing and retry handling are now more defensive
