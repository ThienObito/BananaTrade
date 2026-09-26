from datetime import UTC, datetime

import pandas as pd
import pytest

from bananatrade.data.triggers import (
    atr_expansion,
    evaluate_triggers,
    funding_extreme,
    range_breakout,
    volume_spike,
)


# Boundaries are inclusive: a value exactly equal to a threshold fires.
def test_range_breakout_both_directions() -> None:
    assert range_breakout("BTC/USDT", "1h", 101, 100, 90).direction == "up"
    assert range_breakout("BTC/USDT", "1h", 89, 100, 90).direction == "down"
    assert range_breakout("BTC/USDT", "1h", 95, 100, 90) is None


@pytest.mark.parametrize("price, high, low, expected", [(100.001, 100, 90, True), (99.999, 100, 90, False), (100, 100, 90, True), (89.999, 100, 90, True), (90.001, 100, 90, False), (90, 100, 90, True)])
def test_range_breakout_boundaries(price: float, high: float, low: float, expected: bool) -> None:
    assert (range_breakout("BTC/USDT", "1h", price, high, low) is not None) is expected


@pytest.mark.parametrize("value, threshold, expected", [(2.1, 2.0, True), (1.9, 2.0, False), (2.0, 2.0, True)])
def test_volume_trigger_boundaries(value: float, threshold: float, expected: bool) -> None:
    assert (volume_spike("BTC/USDT", "1h", value, threshold) is not None) is expected


@pytest.mark.parametrize("value, threshold, expected", [(1.1, 1.0, True), (0.9, 1.0, False), (1.0, 1.0, True)])
def test_atr_trigger_boundaries(value: float, threshold: float, expected: bool) -> None:
    assert (atr_expansion("BTC/USDT", "1h", value, threshold) is not None) is expected


@pytest.mark.parametrize("value, threshold, expected, direction", [(0.0021, 0.002, True, "positive"), (-0.0021, 0.002, True, "negative"), (0.0019, 0.002, False, None), (0.002, 0.002, True, "positive"), (-0.002, 0.002, True, "negative"), (-0.0019, 0.002, False, None)])
def test_funding_trigger_boundaries(value: float, threshold: float, expected: bool, direction: str | None) -> None:
    result = funding_extreme("BTC/USDT", "1h", value, threshold)
    assert (result is not None) is expected
    if result is not None:
        assert result.direction == direction


def test_funding_none_no_trigger() -> None:
    assert funding_extreme("BTC/USDT", "1h", None, 0.002) is None


def test_breakout_uses_prior_range() -> None:
    frame = pd.DataFrame({"timestamp_ms": [0, 3_600_000, 7_200_000], "open": [95, 95, 95], "high": [100, 100, 101], "low": [90, 90, 89], "close": [95, 95, 100.5], "volume": [100, 100, 100]})
    as_of = datetime.fromtimestamp(10_800_000 / 1000, UTC)
    triggers = evaluate_triggers("BTC/USDT", {"1h": frame}, None, as_of, {"range_periods": 2, "funding_extreme": 99.0})
    assert any(item.name == "range_breakout" and item.direction == "up" for item in triggers)


@pytest.mark.parametrize("trigger_name", ["range_breakout", "volume_zscore", "atr_expansion"])
def test_trigger_ignores_forming_candle(trigger_name: str) -> None:
    frame = pd.DataFrame({"timestamp_ms": [0, 3_600_000, 7_200_000], "open": [95, 95, 95], "high": [100, 100, 110], "low": [90, 90, 89], "close": [95, 95, 110], "volume": [100, 100, 500]})
    config = {"range_periods": 2, "volume_zscore": 0.5, "atr_expansion_ratio": 1.0, "funding_extreme": 99.0}
    before_close = datetime.fromtimestamp(7_200_000 / 1000 + 1800, UTC)
    after_close = datetime.fromtimestamp(10_800_000 / 1000, UTC)
    assert not any(item.name == trigger_name for item in evaluate_triggers("BTC/USDT", {"1h": frame}, None, before_close, config))
    assert any(item.name == trigger_name for item in evaluate_triggers("BTC/USDT", {"1h": frame}, None, after_close, config))
