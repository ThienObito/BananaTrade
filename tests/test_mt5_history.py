from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from bananatrade.research.mt5_history import fetch_history, validate_history, write_history_set


def bar(timestamp: int, close: float = 10.0, spread: float = 2.0) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "datetime": datetime.fromtimestamp(timestamp, UTC).isoformat(),
        "open": 9.0,
        "high": 11.0,
        "low": 8.0,
        "close": close,
        "spread": spread,
        "tick_volume": 5.0,
        "real_volume": 5.0,
    }


def test_valid_history_accepts_weekend_gap() -> None:
    friday = int(datetime(2024, 1, 5, 23, 45, tzinfo=UTC).timestamp())
    monday = int(datetime(2024, 1, 8, 0, tzinfo=UTC).timestamp())
    result = validate_history([bar(friday), bar(monday)], 15)
    assert result.valid
    assert result.gaps == 0


def test_duplicate_timestamp_is_flagged() -> None:
    result = validate_history([bar(1_700_000_000), bar(1_700_000_000)], 15)
    assert result.duplicates == 1
    assert not result.valid


def test_out_of_order_timestamp_is_flagged() -> None:
    result = validate_history([bar(1_700_000_900), bar(1_700_000_000)], 15)
    assert result.invalid_rows > 0
    assert not result.valid


def test_ohlc_sanity_is_flagged() -> None:
    invalid = bar(1_700_000_000)
    invalid["high"] = 7.0
    result = validate_history([invalid], 15)
    assert result.invalid_rows == 1


def test_spread_sanity_is_flagged() -> None:
    result = validate_history([bar(1_700_000_000, spread=-1)], 15)
    assert result.invalid_rows == 1


def test_weekday_short_gap_is_flagged() -> None:
    start = int(datetime(2024, 1, 8, 10, 0, tzinfo=UTC).timestamp())
    result = validate_history([bar(start), bar(start + 30 * 60)], 15)
    assert result.gaps == 1


def test_write_history_preserves_spread(tmp_path: Path) -> None:
    from bananatrade.research.mt5_history import HistoryValidation, MT5HistorySet

    dataset = MT5HistorySet(
        "XAUUSD", "XAUUSDm", "M15", 15, (bar(1_700_000_000),), HistoryValidation(1, None, None, 0, 0, 0)
    )
    path = write_history_set(dataset, tmp_path)
    assert "spread" in path.read_text(encoding="utf-8").splitlines()[0]
    assert ",2.0," in path.read_text(encoding="utf-8")


def test_fetch_history_resolves_all_requested_sets(tmp_path: Path) -> None:
    class Fake:
        def resolve_symbol(self, symbol):
            return f"{symbol}m"

        def timeframe_value(self, label):
            return 15 if label == "M15" else 16385

        def get_rates_range(self, symbol, timeframe, start, end):
            return [bar(1_700_000_000), bar(1_700_000_900)]

    sets = fetch_history(Fake(), symbols=("XAUUSD", "EURUSD"), timeframes={"M15": 15}, days=1)
    assert [item.name for item in sets] == ["XAUUSDm_M15", "EURUSDm_M15"]
    assert all(len(item.candles) == 2 for item in sets)


def test_fetch_history_rejects_more_than_24_months() -> None:
    with pytest.raises(ValueError, match="exceed"):
        fetch_history(object(), days=731)


def test_empty_history_is_invalid() -> None:
    result = validate_history([], 60)
    assert not result.valid
    assert result.rows == 0
