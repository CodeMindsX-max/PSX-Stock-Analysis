# Recommended Build Order And Developer Task Checklist

## 1. Baseline Verification

Current test status before creating this checklist:

- Date: `2026-04-20`
- Command: `.\venv\Scripts\python.exe -m unittest tests.test_psx_pipeline`
- Result: `7 tests passed`
- Runtime: about `1.3s`

This means the current repository is in a good baseline state for planning the next steps.

## 2. Recommended Build Order

Build or improve the project in this order:

1. Project setup and environment configuration
2. Shared path utilities and storage rules
3. Raw market data ingestion
4. Data cleaning and cumulative history management
5. Feature engineering
6. Model training, evaluation, and versioning
7. Pipeline orchestration and bootstrap recovery
8. Flask API routes and admin protection
9. Dashboard UI and admin tools
10. Testing and CI
11. Deployment hardening for Railway and Vercel
12. Next-level product features like watchlists, alerts, backtesting, and portfolio tools

## 3. Core Build Checklist

### Phase 1: Foundation

- [ ] Confirm Python version and virtual environment setup
- [ ] Keep `requirements.txt` updated and minimal
- [ ] Keep `.gitignore` correct for artifacts and seed files
- [ ] Document setup steps in `README.md`
- [ ] Keep `Procfile` valid for Gunicorn deployment
- [ ] Keep `vercel.json` valid for Vercel routing
- [ ] Keep `api/index.py` as the Vercel entrypoint
- [ ] Verify environment variables are documented

Definition of done:

- local install works from a fresh clone
- app boot command is clear
- deployment entrypoints are valid

### Phase 2: Storage And Path Management

- [ ] Keep `scripts/pipeline_utils.py` as the single source of truth for paths
- [ ] Ensure all data, processed, and model directories auto-create
- [ ] Keep archive naming and retention logic stable
- [ ] Keep model registry JSON handling safe
- [ ] Keep file preview and deletion rules secure
- [ ] Prevent path traversal and unsafe file operations

Definition of done:

- artifacts can be listed, previewed, archived, and pruned safely

### Phase 3: Data Ingestion

- [ ] Keep `scripts/fetch_data.py` resilient to PSX markup changes
- [ ] Validate scraped numeric fields before saving
- [ ] Keep retry logic and request timeout handling
- [ ] Keep `Open_Source` logic clear when open is not directly available
- [ ] Save both latest snapshot and timestamped archive copy
- [ ] Expand scraper tests when new parsing logic is added

Definition of done:

- one valid live snapshot can be fetched and saved reliably

### Phase 4: Cleaning And History

- [ ] Keep `scripts/clean_data.py` strict on required columns
- [ ] Preserve useful extra columns when possible
- [ ] Normalize mixed date formats
- [ ] Clean numeric fields consistently
- [ ] Drop invalid rows with clear handling
- [ ] Remove duplicate dates while keeping the newest row
- [ ] Keep cumulative history growing correctly

Definition of done:

- live data merges cleanly into the active historical dataset

### Phase 5: Feature Engineering

- [ ] Keep `scripts/features.py` aligned with the model’s required features
- [ ] Recompute return, moving averages, volatility, RSI, EMA, and MACD correctly
- [ ] Keep date-based features like day-of-week and month
- [ ] Preserve the latest unlabeled row for prediction
- [ ] Reject datasets with insufficient usable rows
- [ ] Add tests whenever features change

Definition of done:

- `featured_data.csv` is valid for both training and latest-row inference

### Phase 6: Model Training

- [ ] Keep `scripts/train_model.py` deterministic and reproducible
- [ ] Train with time-aware splits
- [ ] Keep holdout metrics and walk-forward metrics
- [ ] Save versioned model files
- [ ] Update `models/model.pkl` as the active alias
- [ ] Append metadata into `models/model_registry.json`
- [ ] Store latest feature snapshot and prediction probabilities
- [ ] Add warnings for suspicious data gaps

Definition of done:

- training produces a valid bundle, current alias, and registry entry

### Phase 7: Pipeline Orchestration

- [ ] Keep `scripts/run_pipeline.py` able to bootstrap missing local artifacts
- [ ] Keep the full pipeline order stable: fetch -> clean -> feature -> train -> archive
- [ ] Ensure pipeline summary is structured and API-friendly
- [ ] Keep archive pruning after successful runs
- [ ] Verify repeated runs maintain cumulative history

Definition of done:

- one command can rebuild the system end to end

### Phase 8: Flask Backend

- [ ] Keep `app.py` routes small and predictable
- [ ] Keep model and data caching logic working
- [ ] Keep health route informative
- [ ] Keep admin token protection on sensitive routes
- [ ] Keep background pipeline execution non-blocking
- [ ] Keep Vercel restrictions explicit for pipeline execution
- [ ] Keep errors JSON-safe and user-readable
- [ ] Add logging for important runtime events

Definition of done:

- app serves public routes, admin routes, and background pipeline state correctly

### Phase 9: Dashboard

- [ ] Keep `static/index.html` aligned with backend responses
- [ ] Keep charts, summary cards, and table rendering stable
- [ ] Keep admin token flow working
- [ ] Keep file manager preview and delete actions working
- [ ] Keep mobile responsiveness usable
- [ ] Keep pipeline polling and refresh logic stable
- [ ] Prevent broken UI when model or data is missing

Definition of done:

- dashboard remains usable for both normal users and admin users

### Phase 10: Testing And CI

- [ ] Keep `tests/test_psx_pipeline.py` passing
- [ ] Add focused test files as modules grow
- [ ] Replace placeholder CI steps with real test execution
- [ ] Run tests before major documentation or deployment changes
- [ ] Add regression tests for each bug fix

Definition of done:

- local tests pass and CI runs a real validation command

### Phase 11: Deployment Readiness

- [ ] Verify Railway startup with Gunicorn
- [ ] Verify Vercel routing through `api/index.py`
- [ ] Confirm `/health` works after deployment
- [ ] Keep required artifacts committed or externally stored
- [ ] Configure `PSX_ADMIN_TOKEN`
- [ ] Configure persistent storage where needed
- [ ] Document platform-specific limitations

Definition of done:

- app can be deployed without manual code fixes

## 4. Developer Task Checklist By Role

### Backend Developer

- [ ] Improve API contracts and response consistency
- [ ] Refactor large `app.py` sections into services or routes when needed
- [ ] Add new protected routes carefully
- [ ] Keep file operations safe
- [ ] Add structured logging

### Data Engineer

- [ ] Improve scraper robustness
- [ ] Keep cumulative data history correct
- [ ] Validate data quality on every pipeline run
- [ ] Add better artifact recovery and archiving
- [ ] Prepare for multi-symbol ingestion later

### ML Engineer

- [ ] Improve model validation
- [ ] Compare baseline vs stronger models
- [ ] Add explainability and risk scoring
- [ ] Add backtesting engine
- [ ] Add drift detection and live prediction evaluation

### Frontend Developer

- [ ] Improve chart readability and interaction
- [ ] Add watchlist and backtest screens later
- [ ] Improve loading, error, and empty states
- [ ] Keep responsive layout strong
- [ ] Keep admin UX clear and safe

### DevOps / Deployment

- [ ] Keep environment variable setup documented
- [ ] Make CI run real tests
- [ ] Prepare persistent storage on Railway
- [ ] Keep Vercel deployment read-focused
- [ ] Add scheduled jobs or worker infrastructure when needed

## 5. Suggested Sprint Order

### Sprint 1: Stabilize The Existing Core

- [ ] keep tests green
- [ ] clean up CI workflow
- [ ] review route error handling
- [ ] review scraper edge cases
- [ ] tighten logging and deployment docs

### Sprint 2: Improve Trust And Visibility

- [ ] add explainability endpoint
- [ ] add risk score
- [ ] improve metrics shown in UI
- [ ] add model health summary

### Sprint 3: Add User Value

- [ ] add watchlists
- [ ] add alerts
- [ ] add multi-symbol support

### Sprint 4: Add Intelligence Features

- [ ] add backtesting engine
- [ ] add prediction history
- [ ] add market brief
- [ ] add news and sentiment

### Sprint 5: Make It Product-Grade

- [ ] add PostgreSQL
- [ ] add Redis and worker queue
- [ ] add scheduled jobs
- [ ] add portfolio tracking
- [ ] add drift monitoring

## 6. Release Checklist

Before any major release:

- [ ] run `.\venv\Scripts\python.exe -m unittest tests.test_psx_pipeline`
- [ ] verify `/health`
- [ ] verify `/predict`
- [ ] verify dashboard loads without visible errors
- [ ] verify admin token routes behave correctly
- [ ] verify pipeline status route works
- [ ] verify artifact files are present
- [ ] verify deployment env vars are set
- [ ] verify Railway or Vercel target-specific behavior
- [ ] update docs if behavior changed

## 7. Best Next Tasks From Today

If you want the most practical next steps after this checklist, do these first:

1. replace placeholder CI test step in `.github/workflows/deploy.yml`
2. split tests into smaller focused files
3. add explainability service and risk score service
4. design PostgreSQL models for users, watchlists, and alerts
5. add watchlist routes and UI
6. add backtesting engine

## 8. Short Summary

Use this file as the working developer checklist:

- build foundation first
- protect data flow and pipeline quality
- keep tests green
- deploy only after health, predict, and dashboard checks pass
- add modern product features in phases, not all at once

This is the safest order to grow the project without breaking what already works.
