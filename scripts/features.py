from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    from scripts.pipeline_utils import CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH
except ModuleNotFoundError:
    from pipeline_utils import CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH


REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
FEATURE_COLUMNS = [
    "High",
    "Low",
    "Close",
    "Volume",
    "Return",
    "MA_7",
    "MA_30",
    "Volatility",
    "Day_Of_Week",
    "Month",
    "Days_Since_Last_Trade",
    "RSI_14",
    "EMA_12",
    "EMA_26",
    "MACD",
]
TARGET_COLUMN = "Target"


def compute_rsi(close_prices: pd.Series, window: int = 14) -> pd.Series:
    delta = close_prices.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.rolling(window=window, min_periods=window).mean()
    average_loss = losses.rolling(window=window, min_periods=window).mean()
    relative_strength = average_gain / average_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + relative_strength))
    return rsi.fillna(50.0)


def create_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    dataframe = pd.read_csv(input_path)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {input_path.name}: {', '.join(missing_columns)}")

    dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

    invalid_rows = dataframe[dataframe[REQUIRED_COLUMNS].isna().any(axis=1)]
    dropped_invalid_rows = len(invalid_rows)
    if dropped_invalid_rows:
        dataframe = dataframe.drop(index=invalid_rows.index)

    if dataframe.empty:
        raise ValueError("No rows remained after validating the cleaned dataset.")

    duplicate_dates = int(dataframe.duplicated(subset=["Date"], keep="last").sum())
    dataframe = dataframe.drop_duplicates(subset=["Date"], keep="last")
    dataframe = dataframe.sort_values(by="Date").reset_index(drop=True)

    dataframe["Return"] = dataframe["Close"].pct_change()
    dataframe["MA_7"] = dataframe["Close"].rolling(7, min_periods=7).mean()
    dataframe["MA_30"] = dataframe["Close"].rolling(30, min_periods=30).mean()
    dataframe["Volatility"] = dataframe["Close"].pct_change().rolling(7, min_periods=7).std()
    dataframe["Day_Of_Week"] = dataframe["Date"].dt.dayofweek
    dataframe["Month"] = dataframe["Date"].dt.month
    dataframe["Days_Since_Last_Trade"] = dataframe["Date"].diff().dt.days.fillna(0).clip(lower=0)
    dataframe["RSI_14"] = compute_rsi(dataframe["Close"], window=14)
    dataframe["EMA_12"] = dataframe["Close"].ewm(span=12, adjust=False).mean()
    dataframe["EMA_26"] = dataframe["Close"].ewm(span=26, adjust=False).mean()
    dataframe["MACD"] = dataframe["EMA_12"] - dataframe["EMA_26"]

    next_close = dataframe["Close"].shift(-1)
    dataframe[TARGET_COLUMN] = pd.Series(pd.NA, index=dataframe.index, dtype="Int64")
    valid_target_mask = next_close.notna()
    dataframe.loc[valid_target_mask, TARGET_COLUMN] = (
        next_close[valid_target_mask] > dataframe.loc[valid_target_mask, "Close"]
    ).astype(int)

    training_ready_rows = dataframe.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    if training_ready_rows.empty:
        raise ValueError("Not enough valid rows were available to create training features.")

    latest_feature_row = dataframe.dropna(subset=FEATURE_COLUMNS).tail(1)
    if latest_feature_row.empty:
        raise ValueError("Latest feature row is not available for API use.")

    serialized = dataframe.copy()
    serialized["Date"] = serialized["Date"].dt.strftime("%Y-%m-%d")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized.to_csv(output_path, index=False)

    serialized.attrs["rows_dropped_for_invalid_values"] = dropped_invalid_rows
    serialized.attrs["duplicate_dates_removed"] = duplicate_dates
    serialized.attrs["feature_columns"] = FEATURE_COLUMNS
    return serialized


if __name__ == "__main__":
    create_features(CURRENT_CLEANED_PATH, CURRENT_FEATURED_PATH)
