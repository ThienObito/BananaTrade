from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from .indicators import atr, range_high, range_low, volume_zscore
from .snapshot import closed_candles


@dataclass(frozen=True)
class Trigger:
    name: str
    symbol: str
    timeframe: str
    value: float
    threshold: float
    direction: str


def range_breakout(symbol: str, timeframe: str, price: float, high: float, low: float) -> Trigger | None:
    if price >= high:
        return Trigger("range_breakout", symbol, timeframe, price, high, "up")
    if price <= low:
        return Trigger("range_breakout", symbol, timeframe, price, low, "down")
    return None


def volume_spike(symbol: str, timeframe: str, zscore: float, threshold: float) -> Trigger | None:
    if zscore >= threshold:
        return Trigger("volume_zscore", symbol, timeframe, zscore, threshold, "up")
    return None


def atr_expansion(symbol: str, timeframe: str, ratio: float, threshold: float) -> Trigger | None:
    if ratio >= threshold:
        return Trigger("atr_expansion", symbol, timeframe, ratio, threshold, "up")
    return None


def funding_extreme(symbol: str, timeframe: str, funding: float | None, threshold: float) -> Trigger | None:
    if funding is None or abs(funding) < threshold:
        return None
    direction = "positive" if funding >= 0 else "negative"
    return Trigger("funding_extreme", symbol, timeframe, funding, threshold, direction)


def evaluate_triggers(symbol: str, ohlcv_by_tf: dict[str, pd.DataFrame], funding: float | None, as_of: datetime, config: dict[str, Any]) -> list[Trigger]:
    """Evaluate configured triggers only on candles closed by as_of."""
    thresholds = config.get("triggers", config)
    result: list[Trigger] = []
    for timeframe, raw in ohlcv_by_tf.items():
        frame = closed_candles(raw, timeframe, as_of)
        if frame.empty:
            continue
        period = int(thresholds.get("range_periods", 20))
        price = float(frame.iloc[-1]["close"])
        # Compare the closed candle with the preceding range. Including the
        # current candle makes an upside breakout impossible unless its close
        # equals its own high (and similarly for downside breakouts).
        prior_high = range_high(frame["high"].shift(1), period)
        prior_low = range_low(frame["low"].shift(1), period)
        high = float(prior_high.iloc[-1])
        low = float(prior_low.iloc[-1])
        if pd.isna(high) or pd.isna(low):
            continue
        breakout = range_breakout(symbol, timeframe, price, high, low)
        if breakout is not None:
            result.append(breakout)
        zscore = volume_zscore(frame["volume"], period).iloc[-1]
        if pd.notna(zscore):
            trigger = volume_spike(symbol, timeframe, float(zscore), float(thresholds.get("volume_zscore", 2.0)))
            if trigger is not None:
                result.append(trigger)
        values = atr(frame, period)
        if len(values) > 1 and pd.notna(values.iloc[-1]) and pd.notna(values.iloc[-2]) and values.iloc[-2] != 0:
            trigger = atr_expansion(symbol, timeframe, float(values.iloc[-1] / values.iloc[-2]), float(thresholds.get("atr_expansion_ratio", 1.5)))
            if trigger is not None:
                result.append(trigger)
        funding_trigger = funding_extreme(symbol, timeframe, funding, float(thresholds.get("funding_extreme", 0.001)))
        if funding_trigger is not None:
            result.append(funding_trigger)
    return result
