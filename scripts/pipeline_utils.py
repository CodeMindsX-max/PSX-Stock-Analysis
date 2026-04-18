from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pickle
import shutil

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

SEED_HISTORY_PATH = RAW_DIR / "Stock Exchange KSE 100(Pakistan).csv"
LATEST_LIVE_RAW_PATH = RAW_DIR / "latest_live_data.csv"
CURRENT_RAW_HISTORY_PATH = RAW_DIR / "market_history_current.csv"
CURRENT_CLEANED_PATH = PROCESSED_DIR / "cleaned_data.csv"
CURRENT_FEATURED_PATH = PROCESSED_DIR / "featured_data.csv"
CURRENT_MODEL_PATH = MODELS_DIR / "model.pkl"

ARCHIVE_LIMIT = 5
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

MANAGED_DIRECTORIES = {
    "raw": RAW_DIR,
    "processed": PROCESSED_DIR,
    "models": MODELS_DIR,
}

PROTECTED_FILES = {
    "raw": {
        SEED_HISTORY_PATH.name,
        LATEST_LIVE_RAW_PATH.name,
        CURRENT_RAW_HISTORY_PATH.name,
    },
    "processed": {
        CURRENT_CLEANED_PATH.name,
        CURRENT_FEATURED_PATH.name,
    },
    "models": {
        CURRENT_MODEL_PATH.name,
    },
}

ARCHIVE_GLOBS = {
    "raw": ("psx_live_*.csv", "market_history_*.csv"),
    "processed": ("cleaned_data_*.csv", "featured_data_*.csv"),
    "models": ("model_*.pkl",),
}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_slug(current_time: datetime | None = None) -> str:
    current_time = current_time or datetime.now()
    return current_time.strftime(TIMESTAMP_FORMAT)


def build_archive_path(category: str, prefix: str, extension: str, stamp: str | None = None) -> Path:
    if category not in MANAGED_DIRECTORIES:
        raise ValueError(f"Unsupported category: {category}")

    stamp = stamp or timestamp_slug()
    directory = ensure_directory(MANAGED_DIRECTORIES[category])
    return directory / f"{prefix}_{stamp}{extension}"


def copy_file(source_path: Path, destination_path: Path) -> Path:
    ensure_directory(destination_path.parent)
    shutil.copy2(source_path, destination_path)
    return destination_path


def prune_old_archives(category: str, keep: int = ARCHIVE_LIMIT) -> list[str]:
    if category not in MANAGED_DIRECTORIES:
        raise ValueError(f"Unsupported category: {category}")

    deleted_files: list[str] = []
    directory = MANAGED_DIRECTORIES[category]

    for pattern in ARCHIVE_GLOBS.get(category, ()):
        archive_files = sorted(
            directory.glob(pattern),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        for old_file in archive_files[keep:]:
            old_file.unlink(missing_ok=True)
            deleted_files.append(old_file.name)

    return deleted_files


def normalize_path_for_ui(path: Path) -> str:
    try:
        return path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_managed_file(category: str, filename: str) -> Path:
    if category not in MANAGED_DIRECTORIES:
        raise ValueError(f"Unsupported category: {category}")

    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError("Invalid filename.")

    file_path = (MANAGED_DIRECTORIES[category] / safe_name).resolve()
    directory = MANAGED_DIRECTORIES[category].resolve()

    if directory not in file_path.parents:
        raise ValueError("File is outside the managed directory.")

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Managed file not found: {filename}")

    return file_path


def list_managed_files() -> dict[str, list[dict[str, object]]]:
    files_by_category: dict[str, list[dict[str, object]]] = {}

    for category, directory in MANAGED_DIRECTORIES.items():
        ensure_directory(directory)
        files: list[dict[str, object]] = []

        for file_path in sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not file_path.is_file():
                continue

            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "relative_path": normalize_path_for_ui(file_path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "extension": file_path.suffix.lower(),
                "can_delete": file_path.name not in PROTECTED_FILES.get(category, set()),
            })

        files_by_category[category] = files

    return files_by_category


def delete_managed_file(category: str, filename: str) -> dict[str, str]:
    file_path = resolve_managed_file(category, filename)

    if file_path.name in PROTECTED_FILES.get(category, set()):
        raise ValueError("Protected files cannot be deleted.")

    file_path.unlink(missing_ok=True)
    return {
        "category": category,
        "filename": filename,
    }


def preview_managed_file(category: str, filename: str, max_rows: int = 10) -> dict[str, object]:
    file_path = resolve_managed_file(category, filename)

    preview: dict[str, object] = {
        "filename": file_path.name,
        "relative_path": normalize_path_for_ui(file_path),
        "extension": file_path.suffix.lower(),
    }

    if file_path.suffix.lower() == ".csv":
        dataframe = pd.read_csv(file_path, nrows=max_rows)
        preview["preview_type"] = "table"
        preview["columns"] = dataframe.columns.tolist()
        preview["rows"] = dataframe.where(pd.notna(dataframe), None).to_dict(orient="records")
        preview["row_count_preview"] = len(dataframe)
        return preview

    if file_path.suffix.lower() == ".pkl":
        with open(file_path, "rb") as model_file:
            payload = pickle.load(model_file)

        preview["preview_type"] = "pickle"
        if isinstance(payload, dict):
            preview["keys"] = sorted(payload.keys())
            metrics = payload.get("metrics")
            if isinstance(metrics, dict):
                preview["metrics"] = metrics
            if payload.get("feature_columns") is not None:
                preview["feature_columns"] = list(payload["feature_columns"])
        else:
            preview["object_type"] = type(payload).__name__
        return preview

    preview["preview_type"] = "text"
    preview["content"] = file_path.read_text(encoding="utf-8", errors="replace")[:4000]
    return preview
