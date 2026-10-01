"""MT5 historical-bar fetching and deterministic history validation."""

from __future__ import annotations

import csv
import itertools
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from pathlib import Path

from ..brokers.mt5_client import MT5Client

MT5_SYMBOLS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY")
MT5_TIMEFRAMES = {"M15": 15, "H1": 60}
MAX_HISTORY_DAYS = 365 * 2


@dataclass(frozen=True)
class HistoryValidation:
    """Validation result for one symbol/timeframe history set."""

    rows: int
    start: str | None
    end: str | None
    gaps: int
    duplicates: int
    invalid_rows: int

    @property
    def valid(self) -> bool:
        """Return whether history contains no duplicate, gap, or invalid rows."""
        return self.rows > 0 and self.gaps == 0 and self.duplicates == 0 and self.invalid_rows == 0


@dataclass(frozen=True)
class MT5HistorySet:
    """Fetched bars plus validation and broker-resolved symbol identity."""

    requested_symbol: str
    symbol: str
    timeframe: str
    timeframe_minutes: int
    candles: tuple[dict[str, object], ...]
    validation: HistoryValidation

    @property
    def name(self) -> str:
        """Return stable research dataset identity."""
        return f"{self.symbol}_{self.timeframe}"


def validate_history(candles: Iterable[dict[str, object]], timeframe_minutes: int) -> HistoryValidation:
    """Validate OHLC/spread rows and flag unexpected intraday gaps.

    Weekend and long exchange-closure gaps are deliberately ignored. Short gaps
    inside active weekdays remain visible for research audit.
    """
    rows = list(candles)
    timestamps = [value for row in rows if isinstance((value := row.get("timestamp")), int) and not isinstance(value, bool)]
    counts = Counter(timestamps)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    invalid_rows = sum(not _valid_ohlc(row) for row in rows)
    ordered = sorted(set(timestamps))
    if timestamps != ordered:
        invalid_rows += 1
    expected = timeframe_minutes * 60
    gaps = sum(_unexpected_gap(left, right, expected) for left, right in itertools.pairwise(ordered))
    start = _iso_timestamp(min(ordered)) if ordered else None
    end = _iso_timestamp(max(ordered)) if ordered else None
    if len(timestamps) != len(rows):
        invalid_rows += len(rows) - len(timestamps)
    return HistoryValidation(len(rows), start, end, gaps, duplicates, invalid_rows)


def fetch_history(
    client: MT5Client,
    *,
    symbols: Iterable[str] = MT5_SYMBOLS,
    timeframes: dict[str, int] | None = None,
    end: datetime | None = None,
    days: int = MAX_HISTORY_DAYS,
    count: int = 0,
) -> tuple[MT5HistorySet, ...]:
    """Fetch and validate requested MT5 history without placing orders."""
    if days <= 0:
        raise ValueError("days must be positive")
    frame_map = timeframes or MT5_TIMEFRAMES
    if any(label not in MT5_TIMEFRAMES for label in frame_map):
        raise ValueError("unsupported MT5 timeframe")
    if days > MAX_HISTORY_DAYS:
        raise ValueError(f"days must not exceed {MAX_HISTORY_DAYS}")
    end_utc = _utc(end or datetime.now(UTC))
    start_utc = end_utc - timedelta(days=days)
    result: list[MT5HistorySet] = []
    for requested in symbols:
        resolved = client.resolve_symbol(requested)
        for timeframe, minutes in frame_map.items():
            timeframe_value = client.timeframe_value(timeframe) if hasattr(client, "timeframe_value") else minutes
            rows = (
                client.get_rates_range(requested, timeframe_value, start_utc, end_utc)
                if hasattr(client, "get_rates_range")
                else client.get_rates(requested, timeframe_value, count or 100_000)
            )
            if rows:
                rows = sorted(rows, key=_timestamp_key)
                rows = _drop_forming_bar(rows, end_utc, minutes)
            validation = validate_history(rows, minutes)
            result.append(
                MT5HistorySet(
                    requested,
                    resolved,
                    timeframe,
                    minutes,
                    tuple(rows),
                    validation,
                )
            )
    return tuple(result)


def write_history_set(dataset: MT5HistorySet, directory: str | Path = "data/history") -> Path:
    """Write one normalized set while retaining per-bar spread points."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"mt5_{dataset.symbol}_{dataset.timeframe}.csv"
    fields = ("timestamp", "datetime", "open", "high", "low", "close", "spread", "tick_volume", "real_volume")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(dataset.candles)
    return path


def _drop_forming_bar(rows: list[dict[str, object]], end_utc: datetime, timeframe_minutes: int) -> list[dict[str, object]]:
    if not rows:
        return []
    last_timestamp = rows[-1].get("timestamp")
    if isinstance(last_timestamp, (int, float)) and not isinstance(last_timestamp, bool):
        seconds = float(last_timestamp) / 1000.0 if float(last_timestamp) > 10_000_000_000 else float(last_timestamp)
        if datetime.fromtimestamp(seconds, UTC) + timedelta(minutes=timeframe_minutes) > end_utc:
            return rows[:-1]
    return rows


def _valid_ohlc(row: dict[str, object]) -> bool:
    values = [row.get(name) for name in ("open", "high", "low", "close", "spread")]
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(float(value)) for value in values):
        return False
    numeric_values = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if len(numeric_values) != 5:
        return False
    volume = row.get("volume", row.get("tick_volume", row.get("real_volume")))
    if not isinstance(volume, (int, float)) or isinstance(volume, bool) or not isfinite(float(volume)) or float(volume) < 0:
        return False
    open_price, high, low, close, spread = numeric_values
    return min(open_price, high, low, close) > 0 and spread >= 0 and high >= max(open_price, close) and low <= min(open_price, close) and high >= low


def _unexpected_gap(left: int, right: int, expected: int) -> int:
    delta = right - left
    if delta <= expected:
        return 0
    left_day = datetime.fromtimestamp(left, UTC).date()
    right_day = datetime.fromtimestamp(right, UTC).date()
    day_span = (right_day - left_day).days
    if left_day.weekday() >= 5 or right_day.weekday() >= 5 or day_span >= 2:
        return 0
    if delta > 3 * 24 * 60 * 60:
        return 0
    return 1


def _timestamp_key(row: dict[str, object]) -> int:
    value = row.get("timestamp")
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("history timestamp must be integer")
    return value


def _iso_timestamp(value: int) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat()


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
