from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import pandas as pd

import app as app_module
from scripts.clean_data import clean_data
from scripts.features import create_features
from scripts.fetch_data import extract_kse100_snapshot_from_html
from scripts.pipeline_utils import delete_managed_file, preview_managed_file, prune_old_archives
import scripts.pipeline_utils as pipeline_utils
from scripts.train_model import train_model


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FetchDataTests(TestCase):
    def test_extract_kse100_snapshot_from_html(self):
        sample_html = (FIXTURES_DIR / "psx_kse100_sample.html").read_text(encoding="utf-8")

        record = extract_kse100_snapshot_from_html(sample_html)

        self.assertEqual(record["Date"], "17-Apr-26")
        self.assertEqual(record["Close"], 173939.01)
        self.assertEqual(record["Change"], 4027.06)
        self.assertEqual(record["Previous_Close"], 169911.95)
        self.assertEqual(record["Open"], 169911.95)
        self.assertEqual(record["Open_Source"], "previous_close_proxy")


class CleanFeatureTrainTests(TestCase):
    def test_local_pipeline_merges_deduplicates_and_trains(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            seed_path = root / "seed.csv"
            live_path = root / "live.csv"
            merged_path = root / "merged.csv"
            cleaned_path = root / "cleaned.csv"
            featured_path = root / "featured.csv"
            model_path = root / "model.pkl"

            dates = pd.date_range("2024-01-01", periods=60, freq="B")
            seed_frame = pd.DataFrame({
                "Date": [date.strftime("%d-%b-%y") for date in dates[:50]],
                "Open": [100 + index for index in range(50)],
                "High": [102 + index for index in range(50)],
                "Low": [99 + index for index in range(50)],
                "Close": [101 + index + ((-1) ** index) for index in range(50)],
                "Change": [((-1) ** index) * 1.0 for index in range(50)],
                "Volume": [1_000_000 + (index * 1000) for index in range(50)],
                "Ticker": ["KSE100"] * 50,
            })
            seed_frame.to_csv(seed_path, index=False)

            live_frame = pd.DataFrame({
                "Date": [
                    dates[49].strftime("%d-%b-%y"),
                    dates[50].strftime("%d-%b-%y"),
                    dates[59].strftime("%d-%b-%y"),
                ],
                "Open": [300.0, 301.0, 305.0],
                "High": [303.0, 304.0, 309.0],
                "Low": [299.0, 300.0, 304.0],
                "Close": [302.0, 299.0, 308.0],
                "Change": [5.0, -3.0, 9.0],
                "Volume": [2_000_000, 2_050_000, 2_100_000],
                "Fetched_At": ["2026-04-18T15:00:00"] * 3,
            })
            live_frame.to_csv(live_path, index=False)

            cleaned = clean_data(live_path, cleaned_path, history_path=seed_path, merged_output_path=merged_path)
            self.assertEqual(len(cleaned), 52)
            self.assertEqual(cleaned["Date"].iloc[-1], dates[59].strftime("%Y-%m-%d"))
            self.assertIn("Ticker", cleaned.columns)
            self.assertIn("Fetched_At", cleaned.columns)

            featured = create_features(cleaned_path, featured_path)
            self.assertIn("Target", featured.columns)
            self.assertIn("RSI_14", featured.columns)
            self.assertIn("MACD", featured.columns)
            self.assertIn("Days_Since_Last_Trade", featured.columns)

            model_bundle = train_model(featured_path, model_path)
            self.assertTrue(model_bundle["training_completed"])
            self.assertNotIn("Open", model_bundle["feature_columns"])
            self.assertIn("holdout", model_bundle["metrics"])
            self.assertIn("walk_forward_folds", model_bundle["metrics"])
            self.assertIn("model_version", model_bundle)
            self.assertIn("latest_prediction_probabilities", model_bundle)


class FileManagementTests(TestCase):
    def test_prune_old_archives_keeps_only_five(self):
        with TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir) / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            for index in range(7):
                file_path = raw_dir / f"psx_live_2024010{index}_000000.csv"
                file_path.write_text("Date,Close\n2024-01-01,100\n", encoding="utf-8")

            with mock.patch.dict(pipeline_utils.MANAGED_DIRECTORIES, {"raw": raw_dir}, clear=False), \
                 mock.patch.dict(pipeline_utils.ARCHIVE_GLOBS, {"raw": ("psx_live_*.csv",)}, clear=False):
                deleted = prune_old_archives("raw", keep=5)

            self.assertEqual(len(deleted), 2)
            self.assertEqual(len(list(raw_dir.glob("psx_live_*.csv"))), 5)

    def test_delete_protected_file_is_blocked_and_preview_csv_works(self):
        with TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir) / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            protected_file = raw_dir / "latest_live_data.csv"
            archive_file = raw_dir / "psx_live_20240101_010101.csv"
            protected_file.write_text("Date,Close\n2024-01-01,100\n", encoding="utf-8")
            archive_file.write_text("Date,Close\n2024-01-01,100\n", encoding="utf-8")

            with mock.patch.dict(pipeline_utils.MANAGED_DIRECTORIES, {"raw": raw_dir}, clear=False), \
                 mock.patch.dict(pipeline_utils.PROTECTED_FILES, {"raw": {"latest_live_data.csv"}}, clear=False):
                preview = preview_managed_file("raw", "psx_live_20240101_010101.csv")
                self.assertEqual(preview["preview_type"], "table")
                self.assertEqual(preview["columns"], ["Date", "Close"])

                with self.assertRaises(ValueError):
                    delete_managed_file("raw", "latest_live_data.csv")


class AppRouteTests(TestCase):
    def test_health_route_works(self):
        client = app_module.app.test_client()
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("pipeline_status", payload)
        self.assertIn("admin_configured", payload)

    def test_admin_routes_require_token(self):
        client = app_module.app.test_client()

        with mock.patch.object(app_module, "ADMIN_TOKEN", "secret-token"):
            unauthorized_response = client.get("/api/files")
            self.assertEqual(unauthorized_response.status_code, 401)

            authorized_response = client.get("/api/files", headers={"X-Admin-Token": "secret-token"})
            self.assertEqual(authorized_response.status_code, 200)

    def test_pipeline_run_returns_accepted_when_background_job_starts(self):
        client = app_module.app.test_client()

        with mock.patch.object(app_module, "ADMIN_TOKEN", "secret-token"), \
             mock.patch.object(app_module, "start_pipeline_job", return_value=True):
            response = client.post("/api/pipeline/run", headers={"X-Admin-Token": "secret-token"})

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIn("message", payload)
