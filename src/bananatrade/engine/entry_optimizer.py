"""Regime-aware limit-entry optimization."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import pandas as pd

from ..data.indicators import atr
from .regime_detector import Regime
from .strategy import SignalResult


@dataclass(frozen=True)
class LimitEntry:
    """One limit-entry price and its bar lifetime."""

    price: float
    expiry_bars: int


class EntryOptimizer:
    """Place directional limit entries a fraction of ATR from the close."""

    offset_atr = 0.3
    expiry_bars = 2

    def compute_limit_entry(
        self,
        signal: SignalResult,
        candles: Sequence[dict[str, object]],
        regime: Regime,
    ) -> LimitEntry | None:
        """Return a limit entry, or skip volatile and non-directional signals."""
        if not isinstance(regime, Regime):
            raise TypeError("regime must be a Regime")
        if regime is Regime.VOLATILE or signal.bias == "NEUTRAL":
            return None
        close = self._close(candles)
        atr14 = self._atr14(candles, close)
        offset = atr14 * self.offset_atr
        if signal.bias == "LONG":
            price = close - offset
        elif signal.bias == "SHORT":
            price = close + offset
        else:
            return None
        return LimitEntry(price, self.expiry_bars)

    @staticmethod
    def _close(candles: Sequence[dict[str, object]]) -> float:
        if not candles:
            raise ValueError("candles must not be empty")
        value = candles[-1].get("close")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value) or value <= 0:
            raise ValueError("latest close must be positive and finite")
        return float(value)

    @classmethod
    def _atr14(cls, candles: Sequence[dict[str, object]], price: float) -> float:
        supplied = candles[-1].get("atr14", candles[-1].get("atr"))
        if isinstance(supplied, (int, float)) and not isinstance(supplied, bool) and isfinite(supplied) and supplied > 0:
            return float(supplied)
        frame = pd.DataFrame(candles)
        required = ("high", "low", "close")
        if all(column in frame for column in required):
            for column in required:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if not frame[list(required)].isna().any().any():
                value = float(atr(frame, 14).iloc[-1])
                if isfinite(value) and value > 0:
                    return value
        return max(price * 0.01, 0.01)
