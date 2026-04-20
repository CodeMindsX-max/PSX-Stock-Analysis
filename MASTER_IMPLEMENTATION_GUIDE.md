# PSX Stock Analysis Master Implementation Guide

## 1. Purpose

This document is the build-from-zero blueprint for the PSX Stock Analysis project in this repository.

Use it when you want to:

- recreate the full project from scratch
- rebuild the system in the correct sequence
- assign work to developers module by module
- test every major feature before moving forward
- make the software deployment-ready for Railway or Vercel

This guide is based on the actual repository structure and current working implementation, but it is written as a stronger and more production-ready implementation plan.

## 2. Product Goal

Build a full-stack PSX market intelligence application that:

- fetches the latest KSE-100 market snapshot from PSX
- stores cumulative market history
- cleans and validates raw data
- creates ML-ready technical features
- trains and versions a classification model
- serves prediction and insight APIs through Flask
- renders a responsive dashboard
- supports protected admin operations
- keeps artifacts manageable for deployment and rollback

## 3. Final System Architecture

End-to-end flow:

`PSX website -> fetch_data.py -> clean_data.py -> features.py -> train_model.py -> run_pipeline.py -> app.py -> static/index.html`

Deployment modes:

1. Railway mode
- full Flask app
- background pipeline allowed
- persistent storage recommended
- best option for live retraining

2. Vercel mode
- Flask served through `api/index.py`
- read-focused deployment
- pipeline execution should stay disabled or be handled outside Vercel
- deploy prebuilt data and model artifacts

## 4. Recommended Build Order

Create the project in this exact order:

1. `requirements.txt`
2. `.gitignore`
3. `README.md`
4. `Procfile`
5. `vercel.json`
6. `api/index.py`
7. `scripts/pipeline_utils.py`
8. `data/raw/`, `data/processed/`, `models/`, `tests/fixtures/`, `static/`
9. seed dataset in `data/raw/Stock Exchange KSE 100(Pakistan).csv`
10. `scripts/fetch_data.py`
11. `scripts/clean_data.py`
12. `scripts/features.py`
13. `scripts/train_model.py`
14. `scripts/run_pipeline.py`
15. `app.py`
16. `static/index.html`
17. `tests/test_psx_pipeline.py`
18. `.github/workflows/deploy.yml`

Do not start with UI first. Build the storage layer, pipeline, and API contracts first, then connect the dashboard.

## 5. Current Repository File Map

### Root

- `app.py`: Flask app, cache loading, routes, admin protection, background pipeline launch
- `api.py`: simple app export
- `api/index.py`: Vercel entrypoint
- `requirements.txt`: Python dependencies
- `Procfile`: Gunicorn startup for Railway and similar platforms
- `vercel.json`: Vercel routing and function configuration
- `README.md`: developer-facing setup and usage documentation
- `IMPLEMENTATION_GUIDE.txt`: older implementation document
- `MASTER_IMPLEMENTATION_GUIDE.md`: this guide

### Scripts

- `scripts/pipeline_utils.py`: paths, archive handling, registry helpers, file management
- `scripts/fetch_data.py`: live PSX scraping and snapshot validation
- `scripts/clean_data.py`: merge raw history and latest live data, normalize schema
- `scripts/features.py`: feature engineering and target generation
- `scripts/train_model.py`: model training, evaluation, versioning, registry update
- `scripts/run_pipeline.py`: bootstrap and full pipeline orchestration

### Storage

- `data/raw/`: seed history, latest live snapshot, cumulative raw history
- `data/processed/`: cleaned and featured datasets
- `models/`: current model alias, versioned model files, model registry

### Frontend

- `static/index.html`: dashboard, charts, admin token handling, file manager

### Tests

- `tests/test_psx_pipeline.py`: integration-heavy regression coverage
- `tests/fixtures/psx_kse100_sample.html`: scraping fixture

## 6. Environment Design

Create a `.env` or deployment environment with these variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `PSX_ADMIN_TOKEN` | Yes for admin actions | Protects pipeline and file-management routes |
| `APP_DATA_DIR` | Optional | Overrides the root data directory |
| `APP_RAW_DIR` | Optional | Overrides raw data directory |
| `APP_PROCESSED_DIR` | Optional | Overrides processed data directory |
| `APP_MODELS_DIR` | Optional | Overrides model directory |
| `APP_SEED_HISTORY_PATH` | Optional | Overrides base seed CSV path |
| `APP_LATEST_LIVE_PATH` | Optional | Overrides latest live snapshot path |
| `APP_CURRENT_HISTORY_PATH` | Optional | Overrides cumulative raw history path |
| `APP_CURRENT_CLEANED_PATH` | Optional | Overrides cleaned CSV path |
| `APP_CURRENT_FEATURED_PATH` | Optional | Overrides featured CSV path |
| `APP_CURRENT_MODEL_PATH` | Optional | Overrides active model alias path |
| `APP_MODEL_REGISTRY_PATH` | Optional | Overrides model registry path |
| `APP_ARCHIVE_LIMIT` | Optional | Number of archived files to keep |
| `PSX_ENABLE_VERCEL_BOOTSTRAP` | Optional | Allows bootstrap on Vercel when set to `1` |
| `VERCEL` / `VERCEL_ENV` | Platform-provided | Detects Vercel runtime |

Recommended local example:

```env
PSX_ADMIN_TOKEN=change-this-secret
APP_ARCHIVE_LIMIT=5
```

Recommended production rule:

- use a persistent volume on Railway
- do not rely on ephemeral filesystem for long-term model/data storage
- on Vercel, deploy prebuilt artifacts or use external storage

## 7. Dependencies To Install First

Start with:

```txt
Flask==3.1.3
beautifulsoup4==4.14.3
requests==2.33.1
pandas==3.0.2
scikit-learn==1.8.0
gunicorn==25.3.0
```

Create virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 8. Step-By-Step Implementation Sequence

### Step 1: Bootstrap The Repository

Create:

- `requirements.txt`
- `.gitignore`
- `README.md`
- `Procfile`
- `vercel.json`
- `api/index.py`

Implement:

- dependency list
- Python cache and virtual environment ignores
- allow committed seed data and current deployment artifacts
- `web: gunicorn app:app` in `Procfile`
- Vercel rewrite to `api/index.py`
- `from app import app` in `api/index.py`

Done when:

- `pip install -r requirements.txt` works
- `gunicorn app:app` is a valid startup command
- Vercel can import `app`

### Step 2: Build Shared Storage And Path Utilities

Create:

- `scripts/pipeline_utils.py`

Implement these constants first:

- `BASE_DIR`
- `DATA_DIR`
- `RAW_DIR`
- `PROCESSED_DIR`
- `MODELS_DIR`
- `SEED_HISTORY_PATH`
- `LATEST_LIVE_RAW_PATH`
- `CURRENT_RAW_HISTORY_PATH`
- `CURRENT_CLEANED_PATH`
- `CURRENT_FEATURED_PATH`
- `CURRENT_MODEL_PATH`
- `MODEL_REGISTRY_PATH`
- `ARCHIVE_LIMIT`

Implement these utility functions:

- `ensure_directory`
- `ensure_app_directories`
- `timestamp_slug`
- `build_archive_path`
- `copy_file`
- `write_json_file`
- `read_json_file`
- `append_model_registry_entry`
- `list_model_registry`
- `get_latest_versioned_model_path`
- `resolve_active_model_path`
- `ensure_seed_history_file`
- `ensure_current_history_file`
- `prune_old_archives`
- `normalize_path_for_ui`
- `resolve_managed_file`
- `list_managed_files`
- `delete_managed_file`
- `preview_managed_file`

Main purpose:

- centralize all file and archive rules
- make the app configurable by environment
- avoid hardcoded paths everywhere else

Done when:

- directories auto-create on startup
- active model can resolve from latest versioned model
- managed files can be listed, previewed, and safely deleted

### Step 3: Create Storage Skeleton And Seed Dataset

Create directories:

- `data/raw/`
- `data/processed/`
- `models/`
- `static/`
- `tests/fixtures/`

Commit these minimum files:

- `data/raw/Stock Exchange KSE 100(Pakistan).csv`
- `data/raw/market_history_current.csv`
- `data/processed/cleaned_data.csv`
- `data/processed/featured_data.csv`
- `models/model.pkl`
- `models/model_registry.json`

Reason:

- fresh clone should still boot
- Vercel needs committed artifacts for prediction routes
- Railway gets immediate startup safety

Done when:

- a fresh clone has enough files for `/health` and `/predict` to work after bootstrap

### Step 4: Build Live PSX Fetching

Create:

- `scripts/fetch_data.py`

Implement helper functions:

- `normalize_line`
- `parse_number`
- `parse_percent`
- `parse_headline_values`
- `parse_change_and_percent`
- `extract_text_lines`
- `find_label_value`
- `find_optional_label_value`
- `parse_as_of_timestamp`
- `find_kse100_block_starts`
- `validate_snapshot`
- `extract_kse100_snapshot_from_html`

Implement main public functions:

- `fetch_data`
- `fetch_and_store_live_snapshot`

Implementation rules:

- use `requests` with timeout and retries
- parse PSX HTML with BeautifulSoup
- validate `High >= Low`
- validate `Close` stays within daily range
- validate `Change` and `Change_Percent`
- if open is missing, use previous close as proxy and mark `Open_Source`
- save archive copy and latest copy

Done when:

- scraper produces one-row DataFrame
- invalid markup raises an error
- latest live CSV is written to disk

### Step 5: Build Data Cleaning And History Merging

Create:

- `scripts/clean_data.py`

Implement:

- `parse_mixed_dates`
- `load_and_align_dataframe`
- `clean_data`

Responsibilities:

- read seed history and live snapshot
- validate required columns
- preserve extra metadata columns when present
- coerce numeric fields
- parse mixed date formats
- drop invalid rows
- drop duplicate dates and keep the newest row
- sort by date
- write cleaned output
- write merged cumulative raw history when requested

Done when:

- history grows cumulatively
- duplicate market dates do not create duplicate rows
- malformed data fails fast

### Step 6: Build Feature Engineering

Create:

- `scripts/features.py`

Implement constants:

- `REQUIRED_COLUMNS`
- `NUMERIC_COLUMNS`
- `FEATURE_COLUMNS`
- `TARGET_COLUMN`

Implement:

- `compute_rsi`
- `create_features`

Feature set to generate:

- `High`
- `Low`
- `Close`
- `Volume`
- `Return`
- `MA_7`
- `MA_30`
- `Volatility`
- `Day_Of_Week`
- `Month`
- `Days_Since_Last_Trade`
- `RSI_14`
- `EMA_12`
- `EMA_26`
- `MACD`

Target logic:

- `Target = 1` if next close is higher than current close
- keep last row unlabeled so API can predict the newest feature row

Done when:

- `featured_data.csv` contains feature columns and target
- latest complete feature row exists for prediction use
- training-ready rows exist after dropping NaNs

### Step 7: Build Model Training And Versioning

Create:

- `scripts/train_model.py`

Implement:

- `build_classifier`
- `compute_metric_summary`
- `evaluate_walk_forward`
- `train_model`

Training design:

- use `RandomForestClassifier`
- use holdout split based on time order
- use walk-forward evaluation with `TimeSeriesSplit`
- compute `accuracy`, `precision`, `recall`, `f1`, `confusion_matrix`
- store latest feature snapshot and latest prediction probabilities
- save a versioned model file
- copy latest version to `models/model.pkl`
- append entry to `models/model_registry.json`

Done when:

- model bundle contains model, metrics, feature columns, latest features, version
- registry grows over time
- current model alias points to latest version

### Step 8: Build Pipeline Orchestration

Create:

- `scripts/run_pipeline.py`

Implement:

- `featured_artifact_is_current`
- `model_artifact_is_current`
- `bootstrap_local_artifacts`
- `run_full_pipeline`

Execution order inside `run_full_pipeline`:

1. ensure current history exists
2. ensure seed history exists
3. fetch latest live snapshot
4. merge and clean data
5. archive cumulative raw history
6. build features
7. archive cleaned and featured outputs
8. train and version the model
9. prune old archives
10. return a structured summary object

Done when:

- one command can rebuild the entire data and model pipeline
- missing local artifacts can be bootstrapped without live fetch
- pipeline returns summary details for API and UI

### Step 9: Build Flask Application Shell

Create:

- `app.py`

Implement runtime state first:

- logging config
- Flask app creation
- admin token detection
- Vercel runtime detection
- locks for pipeline execution and cache access
- in-memory model cache
- in-memory data cache
- pipeline status state

Implement utility functions:

- `normalize_value`
- `dataframe_to_records`
- `get_pipeline_state`
- `update_pipeline_state`
- `has_admin_token_configured`
- `pipeline_execution_supported`
- `should_bootstrap_runtime_state`
- `require_admin_token`
- `load_model_bundle`
- `load_featured_data`
- `refresh_runtime_cache`
- `build_latest_input`
- `run_pipeline_background_job`
- `start_pipeline_job`
- `bootstrap_runtime_state`

Done when:

- app starts without route errors
- bootstrap runs on import
- model and processed data load from cache-aware helpers

### Step 10: Build Public API Routes

Implement these routes in `app.py`:

- `GET /`
- `GET /dashboard`
- `GET /health`
- `GET /api/health`
- `GET /data`
- `GET /api/data`
- `GET /predict`
- `GET /api/predict`
- `GET /insights`
- `GET /api/insights`
- `GET /api/pipeline/status`

Required route behavior:

- `/health` returns model status, data status, admin status, and pipeline state
- `/data` returns recent processed rows
- `/predict` returns prediction, confidence, feature columns, latest features, metrics, and warnings
- `/insights` returns average return and volatility

Done when:

- dashboard can load all public data without admin access

### Step 11: Build Protected Admin Routes

Implement these admin routes in `app.py`:

- `GET /api/files`
- `GET /api/files/preview`
- `POST /api/files/delete`
- `POST /api/pipeline/run`

Security rules:

- protect all admin routes with `@require_admin_token`
- require `X-Admin-Token`
- return `401` for bad token
- return `503` if token is not configured
- never allow protected core files to be deleted

Platform rules:

- on Vercel, `POST /api/pipeline/run` should return a clear disabled message
- on Railway, run pipeline in background thread and return `202`

Done when:

- admin can manage artifacts safely
- pipeline can be started without blocking the request

### Step 12: Build The Frontend Dashboard

Create:

- `static/index.html`

Build these UI areas:

- navigation and status bar
- prediction summary cards
- direction chart
- market structure chart
- recent sessions table
- latest feature snapshot panel
- admin token dialog flow
- file manager modal

Implement these JavaScript functions:

- `formatNumber`
- `formatCompactNumber`
- `formatPercent`
- `formatLocalTimestamp`
- `setStatusChip`
- `getAdminToken`
- `setAdminToken`
- `getAdminHeaders`
- `hasUsableAdminAccess`
- `updateAdminUi`
- `fetchJson`
- `postJson`
- `fetchAdminJson`
- `postAdminJson`
- `buildTrendSeries`
- `createOrUpdateDirectionChart`
- `createOrUpdatePriceChart`
- `renderSnapshotGrid`
- `renderTable`
- `applyPipelineStatus`
- `updateSummaryCards`
- `openFileManager`
- `closeFileManager`
- `formatFileSize`
- `loadFiles`
- `renderPreviewTable`
- `previewFile`
- `deleteFile`
- `renderFileSections`
- `pollPipelineStatusUntilSettled`
- `runPipeline`
- `loadDashboard`
- `tickRefreshCountdown`

Frontend behavior rules:

- poll dashboard every 30 seconds
- poll pipeline status while job is running
- lock admin features until token is entered
- handle missing model/data gracefully
- show warnings clearly
- support mobile and desktop layouts

Done when:

- the entire dashboard can run from Flask static hosting
- admin actions work only with valid token

### Step 13: Build Tests Before Refinement

Create:

- `tests/test_psx_pipeline.py`

Cover these areas first:

- scraper parsing
- data merge and deduplication
- feature creation
- model training
- archive pruning
- protected file deletion rules
- preview behavior
- health route
- admin route auth
- pipeline route accepted response

Recommended next step after initial success:

- split tests into:
  - `tests/test_fetch_data.py`
  - `tests/test_clean_data.py`
  - `tests/test_features.py`
  - `tests/test_train_model.py`
  - `tests/test_app_routes.py`
  - `tests/test_file_management.py`

### Step 14: Add CI

Create or improve:

- `.github/workflows/deploy.yml`

Recommended CI stages:

1. checkout
2. setup Python
3. install dependencies
4. run unit tests
5. optionally build deployment artifact

Current repository note:

- the workflow still contains placeholder test execution
- replace that with a real command:

```bash
python -m unittest tests.test_psx_pipeline
```

## 9. Master Use Cases

### Use Case 1: Public User Views Dashboard

Flow:

1. open `/`
2. frontend loads `/health`, `/predict`, `/insights`, `/data`
3. API returns latest cached model and dataset state
4. dashboard renders charts, cards, and table

Success condition:

- page loads even if admin token is not configured

### Use Case 2: Admin Triggers Pipeline

Flow:

1. admin enters token in UI
2. frontend sends `POST /api/pipeline/run` with `X-Admin-Token`
3. Flask starts background job
4. frontend polls `/api/pipeline/status`
5. on success, dashboard refreshes live data

Success condition:

- request returns immediately and UI never hangs

### Use Case 3: System Rebuilds Missing Artifacts

Flow:

1. app starts
2. `bootstrap_runtime_state()` runs
3. if cleaned or featured data is missing, pipeline bootstrap recreates them
4. if current model is missing, latest version or new training is used

Success condition:

- app recovers from partial artifact loss

### Use Case 4: Admin Reviews Artifacts

Flow:

1. admin opens file manager
2. frontend calls `/api/files`
3. admin previews CSV, JSON, or PKL metadata
4. admin can delete archive files only

Success condition:

- protected files stay safe

### Use Case 5: Deployment Starts Cleanly

Flow:

1. deployment starts Flask app
2. app bootstraps runtime state
3. `/health` confirms readiness
4. dashboard becomes available

Success condition:

- cold start works without manual local fixes

## 10. Master Test Cases

Use these IDs as the baseline QA checklist.

### A. Scraper Tests

- `SCRAPE-001`: valid PSX HTML should produce a complete record
- `SCRAPE-002`: missing KSE100 block should raise parsing error
- `SCRAPE-003`: invalid change math should fail validation
- `SCRAPE-004`: missing open should fall back to previous close and mark `Open_Source`
- `SCRAPE-005`: network retry should fail only after max retries

### B. Cleaning Tests

- `CLEAN-001`: history plus live data should merge into one DataFrame
- `CLEAN-002`: duplicate dates should keep the newest row
- `CLEAN-003`: mixed date formats should parse correctly
- `CLEAN-004`: invalid numeric rows should be dropped
- `CLEAN-005`: extra columns like `Ticker` and `Fetched_At` should be preserved

### C. Feature Tests

- `FEAT-001`: output must include every feature in `FEATURE_COLUMNS`
- `FEAT-002`: final unlabeled row must still exist for prediction
- `FEAT-003`: `RSI_14`, `EMA_12`, `EMA_26`, and `MACD` should be generated
- `FEAT-004`: insufficient rows should raise clear error
- `FEAT-005`: `Days_Since_Last_Trade` should detect multi-day gaps

### D. Model Tests

- `MODEL-001`: training should create a valid model bundle
- `MODEL-002`: bundle must include `model_version`
- `MODEL-003`: bundle must include `feature_columns`
- `MODEL-004`: bundle must include holdout metrics and walk-forward metrics
- `MODEL-005`: model registry must append a new entry after training
- `MODEL-006`: active model alias must point to latest trained version

### E. Pipeline Tests

- `PIPE-001`: full pipeline should fetch, clean, feature, train, and return summary
- `PIPE-002`: bootstrap should rebuild missing artifacts from current history
- `PIPE-003`: pipeline should prune old archives beyond retention limit
- `PIPE-004`: cumulative history should grow after repeated runs

### F. API Tests

- `API-001`: `/health` returns `200`
- `API-002`: `/predict` returns prediction and confidence when model exists
- `API-003`: `/predict` returns meaningful error if model is missing
- `API-004`: `/insights` returns average return and volatility
- `API-005`: `/data` returns recent rows as JSON-safe values
- `API-006`: `/api/pipeline/status` reflects background job state

### G. Security Tests

- `SEC-001`: admin routes should reject missing token
- `SEC-002`: admin routes should reject invalid token
- `SEC-003`: protected files should not be deletable
- `SEC-004`: path traversal attempt in file preview should fail

### H. Frontend Tests

- `UI-001`: dashboard should render without console-breaking API errors
- `UI-002`: admin controls should stay locked until token exists
- `UI-003`: pipeline button should show running state during polling
- `UI-004`: file preview modal should render CSV and JSON content correctly
- `UI-005`: mobile layout should remain usable

### I. Deployment Tests

- `DEP-001`: Railway deployment should boot with Gunicorn
- `DEP-002`: Vercel deployment should route through `api/index.py`
- `DEP-003`: Vercel should block pipeline execution with explicit message
- `DEP-004`: fresh deployment should pass `/health`
- `DEP-005`: committed artifacts should allow immediate prediction response

## 11. Recommended Local Development Routine

Daily development cycle:

1. activate virtual environment
2. pull latest code
3. run tests
4. run `python app.py`
5. open `/health`
6. open dashboard
7. if working on pipeline logic, run `python -m scripts.run_pipeline`
8. rerun tests after changes

Useful commands:

```powershell
python app.py
python -m scripts.run_pipeline
python -m unittest tests.test_psx_pipeline
```

## 12. Deployment Strategy

### Railway Deployment

Best for:

- live pipeline execution
- persistent storage
- background processing

Required setup:

- add all environment variables
- mount persistent storage or point `APP_*` paths to a persistent volume
- deploy with `Procfile` using Gunicorn

Recommended production flow:

1. deploy app
2. set `PSX_ADMIN_TOKEN`
3. mount persistent storage
4. verify `/health`
5. run pipeline once
6. verify `/predict`

### Vercel Deployment

Best for:

- read-only dashboard/API deployment
- serving existing model/data artifacts

Required setup:

- keep `vercel.json`
- keep `api/index.py`
- commit working data and model artifacts
- do not rely on serverless function for long training

Recommended flow:

1. run pipeline locally or on Railway worker
2. commit updated `model.pkl`, `model_registry.json`, and current data files
3. push to Git
4. deploy to Vercel
5. verify `/health`
6. confirm `/api/pipeline/run` is intentionally disabled

## 13. Production Hardening Checklist

Before calling the project deployment-ready, confirm all items below:

- admin token is required for protected routes
- all app paths are environment configurable
- model versioning is working
- old archives are pruned
- `/health` exposes readiness info
- scraper has retry logic
- pipeline is asynchronous
- dashboard handles missing data gracefully
- tests pass locally
- CI runs tests automatically
- persistent storage is configured on Railway
- Vercel is used only for prebuilt inference deployment

## 14. Recommended Improvements Beyond Current Repository

If you want the next version to be more advanced than the current codebase, implement these after the core build is stable:

1. split `app.py` into blueprints and service modules
2. replace in-process background thread with Celery, RQ, or a worker service
3. move artifact metadata to a database
4. add scheduler for daily fetch and retraining
5. add alerting for scraper failures
6. add model comparison and rollback endpoint
7. add richer CI with linting and artifact validation
8. add browser-based UI tests
9. add external object storage for models and data
10. separate frontend into a dedicated app if the dashboard grows

## 15. Short Build Summary

If a new developer asks, "What do I build first?", the answer is:

1. set up dependencies and deployment config
2. build path and storage utilities
3. commit seed data and directory skeleton
4. implement live fetcher
5. implement cleaner and cumulative history
6. implement feature engineering
7. implement training and model versioning
8. implement pipeline orchestration
9. implement Flask APIs and admin protection
10. implement the dashboard
11. implement tests
12. deploy to Railway for full runtime or Vercel for read-only inference

This sequence is the safest path to a robust, full-stack, deployment-ready PSX system.
