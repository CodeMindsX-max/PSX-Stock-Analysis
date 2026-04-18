from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    from scripts.pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_RAW_HISTORY_PATH,
        LATEST_LIVE_RAW_PATH,
        SEED_HISTORY_PATH,
    )
except ModuleNotFoundError:
    from pipeline_utils import (
        CURRENT_CLEANED_PATH,
        CURRENT_RAW_HISTORY_PATH,
        LATEST_LIVE_RAW_PATH,
        SEED_HISTORY_PATH,
    )


REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Change", "Volume"]
NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Change", "Volume"]
KNOWN_DATE_FORMATS = ("%d-%b-%y", "%Y-%m-%d", "%d-%m-%Y", "%b %d, %Y")


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    raw_values = series.astype(str).str.strip()
    parsed_dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    for date_format in KNOWN_DATE_FORMATS:
        remaining_mask = parsed_dates.isna() & raw_values.ne("") & raw_values.ne("nan")
        if remaining_mask.any():
            parsed_dates.loc[remaining_mask] = pd.to_datetime(
                raw_values.loc[remaining_mask],
                format=date_format,
                errors="coerce",
            )

    remaining_mask = parsed_dates.isna() & raw_values.ne("") & raw_values.ne("nan")
    if remaining_mask.any():
        parsed_dates.loc[remaining_mask] = pd.to_datetime(
            raw_values.loc[remaining_mask],
            errors="coerce",
            dayfirst=True,
        )

    return parsed_dates


def load_and_align_dataframe(file_path: str | Path) -> pd.DataFrame:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    dataframe = pd.read_csv(file_path)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {file_path.name}: {', '.join(missing_columns)}")

    return dataframe[REQUIRED_COLUMNS].copy()


def clean_data(
    input_path: str | Path,
    output_path: str | Path,
    history_path: str | Path | None = None,
    merged_output_path: str | Path | None = None,
) -> pd.DataFrame | None:
    try:
        input_path = Path(input_path)
        output_path = Path(output_path)
        history_path = Path(history_path) if history_path else None
        merged_output_path = Path(merged_output_path) if merged_output_path else None

        frames = []
        if history_path:
            frames.append(load_and_align_dataframe(history_path))
        frames.append(load_and_align_dataframe(input_path))

        dataframe = pd.concat(frames, ignore_index=True)

        for column in NUMERIC_COLUMNS:
            cleaned_values = dataframe[column].astype(str).str.replace(",", "", regex=False).str.strip()
            dataframe[column] = pd.to_numeric(cleaned_values, errors="coerce")

        dataframe["Date"] = parse_mixed_dates(dataframe["Date"])

        invalid_rows = dataframe[dataframe[REQUIRED_COLUMNS].isna().any(axis=1)]
        dropped_invalid_rows = len(invalid_rows)
        if dropped_invalid_rows:
            dataframe = dataframe.drop(index=invalid_rows.index)

        if dataframe.empty:
            raise ValueError("No valid rows remained after cleaning numeric and date values.")

        duplicate_dates = int(dataframe.duplicated(subset=["Date"], keep="last").sum())
        dataframe = dataframe.drop_duplicates(subset=["Date"], keep="last")
        dataframe = dataframe.sort_values(by="Date").reset_index(drop=True)

        serialized = dataframe.copy()
        serialized["Date"] = serialized["Date"].dt.strftime("%Y-%m-%d")

        if merged_output_path:
            merged_output_path.parent.mkdir(parents=True, exist_ok=True)
            serialized.to_csv(merged_output_path, index=False)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialized.to_csv(output_path, index=False)

        print("Cleaned data saved to:", output_path)
        print("Rows dropped for invalid values:", dropped_invalid_rows)
        print("Duplicate dates removed:", duplicate_dates)
        return serialized
    except Exception as error:
        print(f"Error while cleaning data: {error}")
        return None


if __name__ == "__main__":
    clean_data(
        LATEST_LIVE_RAW_PATH,
        CURRENT_CLEANED_PATH,
        history_path=SEED_HISTORY_PATH,
        merged_output_path=CURRENT_RAW_HISTORY_PATH,
    )
