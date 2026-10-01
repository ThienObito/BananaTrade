"""Market regime detection from OHLC candles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

import pandas as pd

from ..data.indicators import atr


class Regime(str, Enum):
    """Detected market behavior."""

    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"


@dataclass(frozen=True)
class RegimeSnapshot:
    """Last detector values exposed to dashboard clients."""

    regime: Regime
    adx: float
    atr_pct: float
    confidence: float


class RegimeDetector:
    """Classify candles using ADX and normalized ATR thresholds."""

    def __init__(self) -> None:
        self._last: RegimeSnapshot | None = None

    @property
    def last_regime(self) -> Regime | None:
        """Return most recently detected regime, if any."""
        return self._last.regime if self._last is not None else None

    @property
    def last_snapshot(self) -> RegimeSnapshot | None:
        """Return full most recently detected metrics, if any."""
        return self._last

    def detect(self, candles: list[dict[str, object]]) -> Regime:
        """Detect one regime and retain its metrics."""
        frame = self._frame(candles)
        adx_value = self._adx(frame, 14)
        atr_value = float(atr(frame, 14).iloc[-1])
        price = float(frame["close"].iloc[-1])
        atr_pct = atr_value / price if price > 0 and isfinite(atr_value) else 0.0
        if atr_pct > 0.03:
            regime = Regime.VOLATILE
        elif adx_value > 25.0:
            regime = Regime.TRENDING
        else:
            regime = Regime.RANGING
        confidence = self._confidence(regime, adx_value, atr_pct)
        self._last = RegimeSnapshot(regime, adx_value, atr_pct, confidence)
        return regime

    @staticmethod
    def _frame(candles: list[dict[str, object]]) -> pd.DataFrame:
        if len(candles) < 15:
            raise ValueError("at least 15 candles required")
        frame = pd.DataFrame(candles)
        for column in ("high", "low", "close"):
            if column not in frame:
                raise ValueError(f"missing candle field: {column}")
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[["high", "low", "close"]].isna().any().any():
            raise ValueError("OHLC values must be numeric")
        if (frame["close"] <= 0).any() or (frame[["high", "low"]] < 0).any().any():
            raise ValueError("OHLC values must be non-negative with positive close")
        return frame

    @staticmethod
    def _adx(frame: pd.DataFrame, period: int) -> float:
        high = frame["high"]
        low = frame["low"]
        close = frame["close"]
        up = high.diff()
        down = -low.diff()
        plus_dm = up.where((up > down) & (up > 0), 0.0)
        minus_dm = down.where((down > up) & (down > 0), 0.0)
        previous = close.shift(1)
        true_range = pd.concat([(high - low), (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
        average_range = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / average_range
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / average_range
        denominator = (plus_di + minus_di).replace(0, float("nan"))
        dx = (100 * (plus_di - minus_di).abs() / denominator).fillna(0.0)
        value = float(dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().iloc[-1])
        return value if isfinite(value) else 0.0

    @staticmethod
    def _confidence(regime: Regime, adx_value: float, atr_pct: float) -> float:
        if regime is Regime.TRENDING:
            return min(1.0, max(0.0, adx_value / 50.0))
        if regime is Regime.VOLATILE:
            return min(1.0, max(0.0, atr_pct / 0.1))
        return min(1.0, max(0.0, 1.0 - adx_value / 25.0))
