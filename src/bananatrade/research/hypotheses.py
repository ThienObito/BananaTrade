"""Causal entry hypotheses for historical research."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite, sqrt
from statistics import median
from typing import Literal

from ..engine.regime_detector import Regime, RegimeDetector
from ..engine.strategy import SignalResult

HypothesisName = Literal["H1", "H2", "H3", "H4"]
HYPOTHESES: tuple[HypothesisName, ...] = ("H1", "H2", "H3", "H4")
EXIT_MODELS = ("fixed_2r", "atr_trailing_2x", "time_stop_24")


@dataclass(frozen=True)
class HypothesisStrategy:
    """Generate one entry family from bars available before execution."""

    hypothesis: HypothesisName
    allowed_hours: frozenset[int] | None = None
    lookback: int = 500

    def __post_init__(self) -> None:
        if self.hypothesis not in HYPOTHESES:
            raise ValueError(f"unsupported hypothesis: {self.hypothesis}")
        if self.allowed_hours is not None and any(hour < 0 or hour > 23 for hour in self.allowed_hours):
            raise ValueError("allowed_hours must contain UTC hours from 0 through 23")
        if self.lookback < 1:
            raise ValueError("lookback must be positive")

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        if not candles:
            return _neutral(self.hypothesis, "empty history")
        if self.hypothesis == "H4":
            if self.allowed_hours is None:
                return _neutral("H4", "train UTC hour set is required")
            hour = _utc_hour(candles[-1])
            if hour not in self.allowed_hours:
                return _neutral("H4", "UTC hour outside train volume set")
            for source in ("H1", "H2", "H3"):
                signal = HypothesisStrategy(source).generate_signal(candles)
                if signal.bias != "NEUTRAL":
                    return SignalResult(
                        signal.bias,
                        signal.confidence,
                        f"H4/{source}: {signal.reason}",
                        signal.entry_mode,
                        signal.limit_price,
                        signal.target_price,
                    )
            return _neutral("H4", "H1-H3 union has no signal")
        if self.hypothesis == "H1":
            return self._trend_pullback(candles)
        if self.hypothesis == "H2":
            return self._contraction_breakout(candles)
        return self._range_reversion(candles)

    def _trend_pullback(self, candles: list[dict[str, object]]) -> SignalResult:
        closes = _closes(candles)
        if len(closes) < 55:
            return _neutral("H1", "warmup")
        hourly = _higher_timeframe_closes(candles)
        if len(hourly) < 51:
            return _neutral("H1", "hourly EMA50 warmup")
        ema50 = _ema(hourly, 50)
        ema20 = _ema(closes, 20)
        slope = ema50[-1] - ema50[-2]
        close = closes[-1]
        previous_close = closes[-2]
        current_ema = ema20[-1]
        low = _number(candles[-1].get("low"))
        high = _number(candles[-1].get("high"))
        previous_low = _number(candles[-2].get("low"))
        previous_high = _number(candles[-2].get("high"))
        touch_tolerance = 0.01 * current_ema
        touched_long = low <= current_ema + touch_tolerance or previous_low <= ema20[-2] + touch_tolerance
        touched_short = high >= current_ema - touch_tolerance or previous_high >= ema20[-2] - touch_tolerance
        if slope > 0 and touched_long and close > previous_close and close > current_ema:
            return SignalResult("LONG", _confidence(abs(slope), current_ema), "H1 trend pullback long")
        if slope < 0 and touched_short and close < previous_close and close < current_ema:
            return SignalResult("SHORT", _confidence(abs(slope), current_ema), "H1 trend pullback short")
        return _neutral("H1", "no EMA20 pullback re-entry")

    def _contraction_breakout(self, candles: list[dict[str, object]]) -> SignalResult:
        if len(candles) < 101:
            return _neutral("H2", "warmup")
        atr14 = _atr_series(candles, 14)[-1]
        atr100 = _atr_series(candles, 100)[-1]
        if atr100 <= 0 or not isfinite(atr14 / atr100) or atr14 / atr100 >= 0.7:
            return _neutral("H2", "volatility contraction absent")
        close = _number(candles[-1].get("close"))
        prior_high = max(_number(candle.get("high")) for candle in candles[-21:-1])
        prior_low = min(_number(candle.get("low")) for candle in candles[-21:-1])
        confidence = min(1.0, max(0.0, 1.0 - atr14 / atr100))
        if close > prior_high:
            return SignalResult("LONG", confidence, "H2 contraction breakout above 20-bar high")
        if close < prior_low:
            return SignalResult("SHORT", confidence, "H2 contraction breakout below 20-bar low")
        return _neutral("H2", "20-bar breakout absent")

    def _range_reversion(self, candles: list[dict[str, object]]) -> SignalResult:
        if len(candles) < 22:
            return _neutral("H3", "warmup")
        if not _is_ranging(candles):
            return _neutral("H3", "regime is not RANGING")
        closes = _closes(candles)
        previous_window = closes[-22:-2]
        current_window = closes[-21:-1]
        previous_middle, previous_std = _band(previous_window)
        current_middle, current_std = _band(current_window)
        previous_close = closes[-2]
        current_close = closes[-1]
        previous_lower = previous_middle - 2.0 * previous_std
        previous_upper = previous_middle + 2.0 * previous_std
        current_lower = current_middle - 2.0 * current_std
        current_upper = current_middle + 2.0 * current_std
        if previous_close < previous_lower and current_close >= current_lower:
            return SignalResult("LONG", 0.7, "H3 lower Bollinger re-entry", target_price=current_middle)
        if previous_close > previous_upper and current_close <= current_upper:
            return SignalResult("SHORT", 0.7, "H3 upper Bollinger re-entry", target_price=current_middle)
        return _neutral("H3", "Bollinger re-entry absent")


def top_volume_hours(candles: Sequence[dict[str, object]], count: int = 8) -> frozenset[int]:
    """Return top UTC hours by train-only median volume."""
    if not 1 <= count <= 24:
        raise ValueError("count must be between 1 and 24")
    volumes: dict[int, list[float]] = {hour: [] for hour in range(24)}
    for candle in candles:
        hour = _utc_hour(candle)
        volume = candle.get("volume", 0.0)
        value = float(volume) if isinstance(volume, (int, float)) and isfinite(float(volume)) else 0.0
        volumes[hour].append(max(0.0, value))
    ranked = sorted(volumes, key=lambda hour: (-median(volumes[hour]) if volumes[hour] else 0.0, hour))
    return frozenset(ranked[:count])


def _neutral(hypothesis: str, reason: str) -> SignalResult:
    return SignalResult("NEUTRAL", 0.0, f"{hypothesis}: {reason}")


def _closes(candles: Sequence[dict[str, object]]) -> list[float]:
    return [_number(candle.get("close")) for candle in candles]


def _number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(float(value)):
        raise TypeError("candle value must be finite numeric")
    return float(value)


def _ema(values: Sequence[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def _atr_series(candles: Sequence[dict[str, object]], period: int) -> list[float]:
    if not candles:
        return []
    true_ranges: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        high = _number(candle.get("high"))
        low = _number(candle.get("low"))
        close = _number(candle.get("close"))
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)) if previous_close is not None else high - low)
        previous_close = close
    return _ema(true_ranges, period)


def _higher_timeframe_closes(candles: Sequence[dict[str, object]]) -> list[float]:
    """Return closed UTC-hour bar closes from second- or millisecond timestamps."""
    if not candles:
        return []
    buckets: dict[int, tuple[int, float]] = {}
    for candle in candles:
        raw_timestamp = candle.get("timestamp")
        if not isinstance(raw_timestamp, (int, float)) or isinstance(raw_timestamp, bool):
            continue
        timestamp_seconds = float(raw_timestamp)
        if timestamp_seconds > 10_000_000_000:
            timestamp_seconds /= 1000.0
        hour_bucket = int(timestamp_seconds // 3_600) * 3_600
        buckets[hour_bucket] = (int(timestamp_seconds), _number(candle.get("close")))
    return [buckets[key][1] for key in sorted(buckets)]


def _band(values: Sequence[float]) -> tuple[float, float]:
    middle = sum(values) / len(values)
    deviation = sqrt(sum((value - middle) ** 2 for value in values) / len(values))
    return middle, deviation


def _is_ranging(candles: list[dict[str, object]]) -> bool:
    explicit = candles[-1].get("regime")
    if isinstance(explicit, str):
        return explicit.upper() == Regime.RANGING.value
    try:
        return RegimeDetector().detect(candles) is Regime.RANGING
    except (TypeError, ValueError):
        return False


def _utc_hour(candle: dict[str, object]) -> int:
    value = candle.get("timestamp")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        milliseconds = float(value) if value > 10_000_000_000 else float(value) * 1000.0
        return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC).hour
    return 0


def _confidence(distance: float, price: float) -> float:
    return min(1.0, max(0.5, 0.5 + distance / max(abs(price), 1e-12)))
