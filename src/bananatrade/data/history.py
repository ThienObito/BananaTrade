"""Public Binance historical kline downloader with CSV cache and validation."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import isfinite
from pathlib import Path
from typing import overload
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}
CSV_FIELDS = ("timestamp", "open", "high", "low", "close", "volume", "close_time")

PageFetcher = Callable[[str, str, int, int, int], Sequence[Sequence[object]]]


class HistoryDownloadError(RuntimeError):
    """Raised when public historical data cannot be downloaded or decoded."""


@dataclass(frozen=True)
class HistoryValidation:
    """Validation result for one historical dataset."""

    rows: int
    duplicates: int
    gaps: tuple[int, ...]
    invalid_rows: int = 0

    @property
    def gap_count(self) -> int:
        """Return number of missing expected candle timestamps."""
        return len(self.gaps)


@dataclass(frozen=True)
class HistoryResult(Sequence[dict[str, object]]):
    """Downloaded rows, cache location, and coverage validation."""

    rows: tuple[dict[str, object], ...]
    path: Path
    validation: HistoryValidation
    symbol: str
    interval: str
    start_ms: int
    end_ms: int

    def __len__(self) -> int:
        return len(self.rows)

    @overload
    def __getitem__(self, index: int) -> dict[str, object]: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[dict[str, object]]: ...

    def __getitem__(self, index: int | slice) -> dict[str, object] | Sequence[dict[str, object]]:
        return self.rows[index]

    def __iter__(self) -> Iterator[dict[str, object]]:
        return iter(self.rows)

    @property
    def gaps(self) -> tuple[int, ...]:
        """Return missing candle timestamps."""
        return self.validation.gaps


def download_klines(
    symbol: str,
    interval: str,
    start: datetime | date | str | float,
    end: datetime | date | str | float,
    *,
    cache_dir: str | Path = "data/history",
    fetcher: PageFetcher | None = None,
    limit: int = 1000,
    timeout: float = 30.0,
) -> HistoryResult:
    """Download Binance klines, resuming and updating a symbol/interval CSV cache."""
    normalized_symbol = _symbol(symbol)
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported Binance interval: {interval}")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    start_ms = _timestamp_ms(start)
    end_ms = _timestamp_ms(end)
    if end_ms < start_ms:
        raise ValueError("end must not precede start")
    interval_ms = INTERVAL_MS[interval]
    cache_path = Path(cache_dir) / f"{normalized_symbol}_{interval}.csv"
    cached = _read_cache(cache_path)
    merged: dict[int, dict[str, object]] = {}
    for row in cached:
        timestamp = row.get("timestamp")
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            merged[int(timestamp)] = row
    fetch_page = fetcher or _fetch_page(timeout)
    cursor = _next_fetch_cursor(merged, start_ms, end_ms, interval_ms)
    while cursor <= end_ms:
        try:
            page = fetch_page(normalized_symbol, interval, cursor, end_ms, limit)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, HistoryDownloadError) as exc:
            raise HistoryDownloadError(
                f"Binance klines download failed for {normalized_symbol} {interval} at {cursor}: {exc}"
            ) from exc
        if not page:
            break
        parsed = [_parse_row(item, interval_ms) for item in page]
        filtered: list[dict[str, object]] = []
        for row in parsed:
            timestamp = _row_timestamp(row)
            if timestamp is not None and start_ms <= timestamp <= end_ms:
                filtered.append(row)
        parsed = filtered
        if not parsed:
            break
        before = len(merged)
        for row in parsed:
            timestamp = _row_timestamp(row)
            if timestamp is not None:
                merged[timestamp] = row
        parsed_timestamps = [timestamp for row in parsed if (timestamp := _row_timestamp(row)) is not None]
        newest = max(parsed_timestamps)
        if len(merged) == before and newest < cursor:
            break
        next_cursor = newest + interval_ms
        if next_cursor <= cursor:
            raise HistoryDownloadError("Binance pagination did not advance")
        cursor = next_cursor
    rows = tuple(merged[timestamp] for timestamp in sorted(merged) if start_ms <= timestamp <= end_ms)
    validation = validate_klines(rows, interval, start_ms=start_ms, end_ms=end_ms)
    _write_cache(cache_path, rows)
    _write_validation(cache_path, validation)
    return HistoryResult(rows, cache_path, validation, normalized_symbol, interval, start_ms, end_ms)


def validate_klines(
    rows: Sequence[dict[str, object]],
    interval: str,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> HistoryValidation:
    """Validate timestamp continuity and OHLC sanity without network access."""
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported Binance interval: {interval}")
    interval_ms = INTERVAL_MS[interval]
    seen: set[int] = set()
    duplicates = 0
    invalid = 0
    timestamps: list[int] = []
    for row in rows:
        try:
            timestamp = _int_value(row.get("timestamp"))
            open_price = _float_value(row.get("open"))
            high = _float_value(row.get("high"))
            low = _float_value(row.get("low"))
            close = _float_value(row.get("close"))
            volume = _float_value(row.get("volume"))
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid += 1
            continue
        if timestamp in seen:
            duplicates += 1
        seen.add(timestamp)
        timestamps.append(timestamp)
        if min(open_price, high, low, close) <= 0 or volume < 0 or high < max(open_price, close) or low > min(open_price, close):
            invalid += 1
    unique = sorted(set(timestamps))
    if not unique:
        return HistoryValidation(0, duplicates, (), invalid)
    expected_start = unique[0] if start_ms is None else ((start_ms + interval_ms - 1) // interval_ms) * interval_ms
    expected_end = unique[-1] if end_ms is None else (end_ms // interval_ms) * interval_ms
    expected = set(range(expected_start, expected_end + 1, interval_ms))
    gaps = tuple(sorted(expected - set(unique)))
    return HistoryValidation(len(rows), duplicates, gaps, invalid)


def _row_timestamp(row: dict[str, object]) -> int | None:
    value = row.get("timestamp")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be non-empty")
    normalized = symbol.replace("/", "").replace("-", "").strip().upper()
    if not normalized.isalnum():
        raise ValueError("symbol must contain letters and digits")
    return normalized


def _timestamp_ms(value: datetime | date | str | float) -> int:
    if isinstance(value, datetime):
        resolved = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return int(resolved.timestamp() * 1000)
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return _timestamp_ms(parsed)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return int(number if number > 10_000_000_000 else number * 1000)
    raise TypeError("timestamp must be datetime, date, ISO string, or number")


def _next_fetch_cursor(merged: dict[int, dict[str, object]], start_ms: int, end_ms: int, interval_ms: int) -> int:
    aligned_start = ((start_ms + interval_ms - 1) // interval_ms) * interval_ms
    if not merged:
        return aligned_start
    timestamps = sorted(timestamp for timestamp in merged if aligned_start <= timestamp <= end_ms)
    if not timestamps:
        return aligned_start
    expected = set(range(aligned_start, min(end_ms, timestamps[-1]) + 1, interval_ms))
    missing = sorted(expected - set(timestamps))
    return missing[0] if missing else timestamps[-1] + interval_ms


def _parse_row(row: Sequence[object], interval_ms: int) -> dict[str, object]:
    if len(row) < 7:
        raise ValueError("Binance kline row needs seven fields")
    values = [row[0], row[1], row[2], row[3], row[4], row[5], row[6]]
    timestamp = _int_value(values[0])
    close_time = _int_value(values[6])
    parsed: dict[str, object] = {
        "timestamp": timestamp,
        "open": _finite_float(values[1]),
        "high": _finite_float(values[2]),
        "low": _finite_float(values[3]),
        "close": _finite_float(values[4]),
        "volume": _finite_float(values[5]),
        "close_time": close_time,
    }
    if timestamp % interval_ms != 0 or close_time < timestamp:
        raise ValueError("Binance kline timestamps are invalid")
    volume = parsed.get("volume")
    if isinstance(volume, (int, float)) and not isinstance(volume, bool) and volume < 0:
        raise ValueError("Binance kline volume is negative")
    return parsed


def _int_value(value: object) -> int:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TypeError("value must be numeric")
    return int(value)


def _float_value(value: object) -> float:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TypeError("value must be numeric")
    return float(value)


def _finite_float(value: object) -> float:
    result = _float_value(value)
    if not isfinite(result):
        raise ValueError("numeric value must be finite")
    return result


def _read_cache(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            return [
                _parse_row(
                    [row[field] for field in ("timestamp", "open", "high", "low", "close", "volume", "close_time")],
                    1,
                )
                for row in csv.DictReader(handle)
            ]
    except (OSError, csv.Error, KeyError, TypeError, ValueError) as exc:
        raise HistoryDownloadError(f"history cache read failed: {path}: {exc}") from exc


def _write_cache(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_validation(path: Path, validation: HistoryValidation) -> None:
    report_path = path.with_suffix(".validation.json")
    report_path.write_text(
        json.dumps(
            {
                "rows": validation.rows,
                "duplicates": validation.duplicates,
                "gap_count": validation.gap_count,
                "gaps": list(validation.gaps),
                "invalid_rows": validation.invalid_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _fetch_page(timeout: float) -> PageFetcher:
    def fetch(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int) -> Sequence[Sequence[object]]:
        query = urlencode({"symbol": symbol, "interval": interval, "startTime": start_ms, "endTime": end_ms, "limit": limit})
        request = Request(f"{BINANCE_KLINES_URL}?{query}", headers={"User-Agent": "BananaTrade-research/0.2"})
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HistoryDownloadError(str(exc)) from exc
        if not isinstance(payload, list):
            raise HistoryDownloadError(f"Binance returned non-list payload: {payload}")
        return payload

    return fetch
