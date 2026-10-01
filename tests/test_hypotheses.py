from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bananatrade.research.hypotheses import (
    EXIT_MODELS,
    HYPOTHESES,
    HypothesisStrategy,
    top_volume_hours,
)


def candle(
    close: float,
    *,
    timestamp: int,
    spread: float = 1.0,
    volume: float = 100.0,
    regime: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "timestamp": timestamp,
        "open": close,
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": volume,
        "atr14": max(spread, 0.1),
    }
    if regime is not None:
        row["regime"] = regime
    return row


def hourly_rows(count: int = 160, close: float = 100.0) -> list[dict[str, object]]:
    start = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
    return [candle(close + index * 0.1, timestamp=start + index * 3_600_000) for index in range(count)]


def test_hypothesis_and_exit_catalogs_are_exact() -> None:
    assert HYPOTHESES == ("H1", "H2", "H3", "H4")
    assert EXIT_MODELS == ("fixed_2r", "atr_trailing_2x", "time_stop_24")


def test_empty_history_is_neutral() -> None:
    assert HypothesisStrategy("H1").generate_signal([]).bias == "NEUTRAL"


def test_h1_warmup_is_neutral() -> None:
    assert HypothesisStrategy("H1").generate_signal(hourly_rows(54)).bias == "NEUTRAL"


def test_h1_long_pullback_reentry() -> None:
    rows = hourly_rows()
    ema20_level = float(rows[-1]["close"])
    rows[-2] = candle(ema20_level - 1.4, timestamp=int(rows[-2]["timestamp"]), spread=0.5)
    rows[-1] = candle(ema20_level + 0.2, timestamp=int(rows[-1]["timestamp"]), spread=0.8)
    assert HypothesisStrategy("H1").generate_signal(rows).bias == "LONG"


def test_h1_short_pullback_reentry() -> None:
    rows = hourly_rows()
    rows = [candle(120.0 - index * 0.1, timestamp=int(row["timestamp"])) for index, row in enumerate(rows)]
    ema20_level = float(rows[-1]["close"])
    rows[-2] = candle(ema20_level + 1.4, timestamp=int(rows[-2]["timestamp"]), spread=0.5)
    rows[-1] = candle(ema20_level - 0.2, timestamp=int(rows[-1]["timestamp"]), spread=0.8)
    assert HypothesisStrategy("H1").generate_signal(rows).bias == "SHORT"


def test_h1_requires_touch_and_reentry() -> None:
    rows = hourly_rows()
    rows[-2] = candle(float(rows[-2]["close"]) + 3.0, timestamp=int(rows[-2]["timestamp"]), spread=0.01)
    rows[-1] = candle(float(rows[-1]["close"]) + 3.0, timestamp=int(rows[-1]["timestamp"]), spread=0.01)
    assert HypothesisStrategy("H1").generate_signal(rows).bias == "NEUTRAL"


def contraction_rows() -> list[dict[str, object]]:
    rows = hourly_rows(150)
    for index in range(120, 149):
        rows[index] = candle(100.0, timestamp=int(rows[index]["timestamp"]), spread=0.1)
    rows[-1] = candle(101.0, timestamp=int(rows[-1]["timestamp"]), spread=0.1)
    return rows


def test_h2_warmup_is_neutral() -> None:
    assert HypothesisStrategy("H2").generate_signal(hourly_rows(100)).bias == "NEUTRAL"


def test_h2_contraction_breaks_up() -> None:
    assert HypothesisStrategy("H2").generate_signal(contraction_rows()).bias == "LONG"


def test_h2_requires_contraction() -> None:
    rows = [candle(100.0 + index * 0.05, timestamp=index * 3_600_000, spread=2.0) for index in range(150)]
    assert HypothesisStrategy("H2").generate_signal(rows).bias == "NEUTRAL"


def test_h2_breakout_direction_is_short() -> None:
    rows = contraction_rows()
    rows[-1] = candle(99.0, timestamp=int(rows[-1]["timestamp"]), spread=0.1)
    assert HypothesisStrategy("H2").generate_signal(rows).bias == "SHORT"


def range_rows() -> list[dict[str, object]]:
    start = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rows = [candle(100.0, timestamp=start + index * 3_600_000, regime="RANGING") for index in range(25)]
    rows[-2] = candle(97.0, timestamp=int(rows[-2]["timestamp"]), regime="RANGING")
    rows[-1] = candle(99.5, timestamp=int(rows[-1]["timestamp"]), regime="RANGING")
    return rows


def test_h3_lower_band_reentry_goes_long() -> None:
    result = HypothesisStrategy("H3").generate_signal(range_rows())
    assert result.bias == "LONG"
    assert result.target_price is not None


def test_h3_non_ranging_regime_blocks_signal() -> None:
    rows = range_rows()
    for row in rows:
        row["regime"] = "TRENDING"
    assert HypothesisStrategy("H3").generate_signal(rows).bias == "NEUTRAL"


def test_h3_warmup_is_neutral() -> None:
    assert HypothesisStrategy("H3").generate_signal(range_rows()[:21]).bias == "NEUTRAL"


def test_h3_upper_band_reentry_goes_short() -> None:
    rows = range_rows()
    rows[-2] = candle(103.0, timestamp=int(rows[-2]["timestamp"]), regime="RANGING")
    rows[-1] = candle(100.5, timestamp=int(rows[-1]["timestamp"]), regime="RANGING")
    assert HypothesisStrategy("H3").generate_signal(rows).bias == "SHORT"


def test_h4_requires_train_hour_set() -> None:
    assert HypothesisStrategy("H4").generate_signal(range_rows()).bias == "NEUTRAL"


def test_h4_restricts_signal_to_allowed_hours() -> None:
    rows = range_rows()
    current_hour = datetime.fromtimestamp(int(rows[-1]["timestamp"]) / 1000, tz=UTC).hour
    allowed = frozenset({current_hour})
    assert HypothesisStrategy("H4", allowed_hours=allowed).generate_signal(rows).bias == "LONG"


def test_top_volume_hours_returns_eight_train_hours() -> None:
    rows = hourly_rows(48)
    for index, row in enumerate(rows):
        row["volume"] = float((index % 24) + 1)
    assert len(top_volume_hours(rows)) == 8


def test_top_volume_hours_is_deterministic_on_ties() -> None:
    rows = hourly_rows(24)
    assert top_volume_hours(rows) == frozenset(range(8))


def test_invalid_hypothesis_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        HypothesisStrategy("H9")


def test_invalid_hour_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="UTC hours"):
        HypothesisStrategy("H4", allowed_hours=frozenset({24}))


def test_invalid_top_hour_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="between 1 and 24"):
        top_volume_hours(hourly_rows(), 0)
