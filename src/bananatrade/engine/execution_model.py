"""Regime-aware paper-trade entry and protective-level calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import ClassVar

import pandas as pd

from ..data.indicators import atr
from .position_sizer import PositionSizer
from .regime_detector import Regime
from .strategy import SignalResult


@dataclass(frozen=True)
class EntryParams:
    """Calculated paper entry parameters."""

    price: float
    sl: float
    tp: float
    qty: int


class ExecutionModel:
    """Calculate entries, protective levels, and fixed-risk quantities."""

    SL_MULTIPLIERS: ClassVar[Mapping[Regime, float]] = MappingProxyType(
        {
            Regime.TRENDING: 1.5,
            Regime.RANGING: 1.0,
            Regime.VOLATILE: 2.5,
        }
    )
    TP_MULTIPLIERS: ClassVar[Mapping[Regime, float]] = MappingProxyType(
        {
            Regime.TRENDING: 3.0,
            Regime.RANGING: 2.0,
            Regime.VOLATILE: 0.0,
        }
    )

    def __init__(
        self,
        initial_equity: float = 10_000.0,
        risk_pct: float = 0.01,
        *,
        equity: float | None = None,
    ) -> None:
        resolved_equity = initial_equity if equity is None else equity
        if not isfinite(resolved_equity) or resolved_equity <= 0:
            raise ValueError("initial_equity must be positive and finite")
        if not isfinite(risk_pct) or risk_pct < 0:
            raise ValueError("risk_pct must be non-negative and finite")
        self.initial_equity = float(resolved_equity)
        self.risk_pct = float(risk_pct)

    def compute_entry(
        self,
        signal: SignalResult,
        candles: Sequence[dict[str, object]],
        regime: Regime,
        *,
        equity: float | None = None,
        risk_pct: float | None = None,
        entry_price: float | None = None,
    ) -> EntryParams | None:
        """Calculate one directional entry, or skip neutral/volatile signals."""
        normalized_regime = self._regime(regime)
        if normalized_regime is Regime.VOLATILE or signal.bias == "NEUTRAL":
            return None
        price = self._entry_price(candles, entry_price)
        atr14 = self._atr14(candles, price)
        sl_distance = atr14 * self.SL_MULTIPLIERS[normalized_regime]
        tp_distance = atr14 * self.TP_MULTIPLIERS[normalized_regime]
        if signal.bias == "LONG":
            stop_loss = price - sl_distance
            take_profit = price + tp_distance
        elif signal.bias == "SHORT":
            stop_loss = price + sl_distance
            take_profit = price - tp_distance
        else:
            return None
        quantity = PositionSizer.compute_qty(
            float(self.initial_equity if equity is None else equity),
            price,
            stop_loss,
            self.risk_pct if risk_pct is None else risk_pct,
        )
        return EntryParams(price, stop_loss, take_profit, quantity)

    @staticmethod
    def _regime(regime: Regime) -> Regime:
        if isinstance(regime, Regime):
            return regime
        raise TypeError("regime must be a Regime")

    @classmethod
    def _entry_price(cls, candles: Sequence[dict[str, object]], entry_price: float | None) -> float:
        if entry_price is not None:
            if not isfinite(entry_price) or entry_price <= 0:
                raise ValueError("entry price must be positive and finite")
            return float(entry_price)
        return cls._current_close(candles)

    @staticmethod
    def _current_close(candles: Sequence[dict[str, object]]) -> float:
        if not candles:
            raise ValueError("candles must not be empty")
        value = candles[-1].get("close")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value) or value <= 0:
            raise ValueError("latest close must be positive and finite")
        return float(value)

    @classmethod
    def _atr14(cls, candles: Sequence[dict[str, object]], price: float) -> float:
        latest = candles[-1]
        supplied = latest.get("atr14", latest.get("atr"))
        if isinstance(supplied, (int, float)) and not isinstance(supplied, bool) and isfinite(supplied) and supplied > 0:
            return float(supplied)
        frame = pd.DataFrame(candles)
        if all(column in frame for column in ("high", "low", "close")):
            for column in ("high", "low", "close"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if not frame[["high", "low", "close"]].isna().any().any():
                value = float(atr(frame, 14).iloc[-1])
                if isfinite(value) and value > 0:
                    return value
        return max(price * 0.01, 0.01)
