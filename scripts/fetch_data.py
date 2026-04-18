from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from scripts.pipeline_utils import LATEST_LIVE_RAW_PATH, build_archive_path, copy_file
except ModuleNotFoundError:
    from pipeline_utils import LATEST_LIVE_RAW_PATH, build_archive_path, copy_file


PSX_SOURCE_URL = "https://dps.psx.com.pk/"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

NUMBER_PATTERN = re.compile(r"[-+]?[0-9][0-9,]*\.?[0-9]*")
VALUE_LINE_PATTERN = re.compile(r"^[#\d\-\+]")


class FetchDataError(RuntimeError):
    pass


def normalize_line(text: str) -> str:
    return " ".join(text.split())


def parse_number(value: str) -> float:
    match = NUMBER_PATTERN.search(value.replace("%", ""))
    if not match:
        raise FetchDataError(f"Could not parse numeric value from: {value}")

    return float(match.group(0).replace(",", ""))


def parse_percent(value: str) -> float:
    if "%" not in value:
        raise FetchDataError(f"Could not parse percentage value from: {value}")
    return parse_number(value)


def parse_headline_values(line: str) -> tuple[float, float, float]:
    matches = NUMBER_PATTERN.findall(line.replace("%", ""))
    if len(matches) < 3:
        raise FetchDataError(f"Could not parse the KSE100 headline block: {line}")

    current_value = float(matches[0].replace(",", ""))
    change_value = float(matches[1].replace(",", ""))
    change_percent = float(matches[2].replace(",", ""))
    return current_value, change_value, change_percent


def parse_change_and_percent(line: str) -> tuple[float, float]:
    matches = NUMBER_PATTERN.findall(line.replace("%", ""))
    if len(matches) < 2:
        raise FetchDataError(f"Could not parse change and percent values from: {line}")

    change_value = float(matches[0].replace(",", ""))
    change_percent = float(matches[1].replace(",", ""))
    return change_value, change_percent


def extract_text_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [normalize_line(line) for line in soup.stripped_strings if normalize_line(line)]


def find_label_value(lines: list[str], start_index: int, label: str) -> float:
    for index in range(start_index, min(start_index + 30, len(lines) - 1)):
        if lines[index] == label:
            return parse_number(lines[index + 1])
    raise FetchDataError(f"Could not find label '{label}' in the PSX response.")


def parse_as_of_timestamp(lines: list[str], start_index: int) -> tuple[datetime, int]:
    for index in range(start_index, min(start_index + 20, len(lines))):
        if lines[index].startswith("As of "):
            timestamp = datetime.strptime(lines[index].replace("As of ", ""), "%b %d, %Y %I:%M %p")
            return timestamp, index
    raise FetchDataError("Could not locate the 'As of' timestamp for KSE100.")


def find_kse100_block_starts(lines: list[str]) -> list[int]:
    candidate_starts: list[int] = []

    for index, line in enumerate(lines):
        if line == "KSE100" and index + 1 < len(lines):
            next_line = lines[index + 1]
            if VALUE_LINE_PATTERN.match(next_line):
                candidate_starts.append(index)

    indices_headers = [
        index for index, line in enumerate(lines) if line in {"Indices", "# Indices"}
    ]

    for indices_header in indices_headers:
        index_names: list[str] = []
        first_data_index = None
        for index in range(indices_header + 1, len(lines)):
            line = lines[index]
            if line.startswith("As of ") or line in {"High", "Low", "Volume", "Previous Close"}:
                first_data_index = index
                break
            if VALUE_LINE_PATTERN.match(line):
                first_data_index = index
                break
            index_names.append(line)

        if first_data_index is None or "KSE100" not in index_names:
            continue

        block_starts = [
            index - 2
            for index in range(first_data_index, len(lines))
            if lines[index].startswith("As of ") and index >= 2
        ]
        kse100_position = index_names.index("KSE100")
        if kse100_position < len(block_starts):
            candidate_starts.append(block_starts[kse100_position])

    unique_candidates = list(dict.fromkeys(candidate_starts))
    if not unique_candidates:
        raise FetchDataError("Could not locate a KSE100 candidate block in the PSX response.")

    return unique_candidates


def validate_snapshot(record: dict[str, object]) -> None:
    high = float(record["High"])
    low = float(record["Low"])
    close = float(record["Close"])
    change = float(record["Change"])
    previous_close = float(record["Previous_Close"])
    change_percent = float(record["Change_Percent"])
    volume = float(record["Volume"])

    if high < low:
        raise FetchDataError("Fetched PSX data is invalid: High is less than Low.")

    if close < low or close > high:
        raise FetchDataError("Fetched PSX data is invalid: Close is outside the day range.")

    if volume < 0:
        raise FetchDataError("Fetched PSX data is invalid: Volume cannot be negative.")

    expected_change = round(close - previous_close, 2)
    if abs(expected_change - change) > 1.0:
        raise FetchDataError(
            "Fetched PSX data failed validation: Change does not match current and previous close."
        )

    expected_change_percent = round((change / previous_close) * 100, 2) if previous_close else 0.0
    if abs(expected_change_percent - change_percent) > 0.5:
        raise FetchDataError(
            "Fetched PSX data failed validation: Change percent does not match change and previous close."
        )


def extract_kse100_snapshot_from_html(html: str) -> dict[str, object]:
    lines = extract_text_lines(html)
    block_starts = find_kse100_block_starts(lines)

    for start_index in block_starts:
        try:
            if lines[start_index].startswith("#"):
                current_value, change_value, change_percent = parse_headline_values(lines[start_index])
                search_start = start_index
            elif lines[start_index + 1].startswith("#"):
                current_value, change_value, change_percent = parse_headline_values(lines[start_index + 1])
                search_start = start_index + 1
            elif "%" in lines[start_index + 1]:
                current_value = parse_number(lines[start_index])
                change_value, change_percent = parse_change_and_percent(lines[start_index + 1])
                search_start = start_index
            else:
                current_value = parse_number(lines[start_index + 1])
                if "%" in lines[start_index + 2]:
                    change_value, change_percent = parse_change_and_percent(lines[start_index + 2])
                else:
                    change_value = parse_number(lines[start_index + 2])
                    change_percent = parse_percent(lines[start_index + 3])
                search_start = start_index

            as_of_timestamp, as_of_index = parse_as_of_timestamp(lines, search_start)

            high_value = find_label_value(lines, as_of_index, "High")
            low_value = find_label_value(lines, as_of_index, "Low")
            volume_value = find_label_value(lines, as_of_index, "Volume")
            previous_close = find_label_value(lines, as_of_index, "Previous Close")

            record = {
                "Date": as_of_timestamp.strftime("%d-%b-%y"),
                "Open": round(previous_close, 2),
                "High": round(high_value, 2),
                "Low": round(low_value, 2),
                "Close": round(current_value, 2),
                "Change": round(change_value, 2),
                "Volume": int(round(volume_value)),
                "Previous_Close": round(previous_close, 2),
                "Change_Percent": round(change_percent, 2),
                "Fetched_At": datetime.now().isoformat(timespec="seconds"),
                "Source_URL": PSX_SOURCE_URL,
                "Open_Source": "previous_close_proxy",
            }

            validate_snapshot(record)
            return record
        except (FetchDataError, ValueError, IndexError):
            continue

    raise FetchDataError("Could not locate a validated KSE100 block in the PSX HTML response.")


def fetch_data(
    output_path: str | Path | None = None,
    html: str | None = None,
    timeout: int = 30,
) -> dict[str, object]:
    if html is None:
        response = requests.get(PSX_SOURCE_URL, headers=REQUEST_HEADERS, timeout=timeout)
        response.raise_for_status()
        html = response.text

    record = extract_kse100_snapshot_from_html(html)
    dataframe = pd.DataFrame([record])

    saved_path = None
    if output_path is not None:
        saved_path = Path(output_path)
        saved_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(saved_path, index=False)

    return {
        "record": record,
        "dataframe": dataframe,
        "output_path": str(saved_path) if saved_path else None,
    }


def fetch_and_store_live_snapshot() -> dict[str, object]:
    archive_path = build_archive_path("raw", "psx_live", ".csv")
    fetch_result = fetch_data(output_path=archive_path)
    copy_file(archive_path, LATEST_LIVE_RAW_PATH)

    fetch_result["archive_path"] = str(archive_path)
    fetch_result["latest_path"] = str(LATEST_LIVE_RAW_PATH)
    return fetch_result


if __name__ == "__main__":
    try:
        result = fetch_and_store_live_snapshot()
        print("Live PSX data fetched successfully.")
        print("Archived raw file:", result["archive_path"])
        print("Latest raw file:", result["latest_path"])
    except Exception as error:
        print(f"Error while fetching PSX data: {error}")
