"""Ensemble-backed paper-trading strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from .ensemble_signal import EnsembleSignal
from .regime_detector import Regime


@dataclass(frozen=True)
class SignalResult:
    """Strategy decision produced from closed candles."""

    bias: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float
    reason: str
    entry_mode: Literal["market", "limit"] = "market"
    limit_price: float | None = None
    target_price: float | None = None


class MACrossStrategy:
    """Keep legacy strategy interface while using ensemble scoring internally."""

    def __init__(
        self,
        ensemble: EnsembleSignal | None = None,
        ma_fast: int = 20,
        ma_slow: int = 50,
    ) -> None:
        self.ensemble = ensemble or EnsembleSignal(ma_fast=ma_fast, ma_slow=ma_slow)

    def generate_signal(
        self,
        candles: list[dict[str, object]] | tuple[dict[str, object], ...] | pd.DataFrame,
    ) -> SignalResult:
        """Return one ensemble signal from closed candles."""
        records = candles.to_dict("records") if isinstance(candles, pd.DataFrame) else list(candles)
        score = self.ensemble.score(records)
        regime = self.ensemble.regime_detector.last_regime
        rsi_value = self.ensemble.last_rsi
        if score.bias == "NEUTRAL" and rsi_value is not None and rsi_value >= 70:
            reason = "bullish crossover blocked by overbought RSI"
        elif score.bias == "NEUTRAL" and rsi_value is not None and rsi_value <= 30:
            reason = "bearish crossover blocked by oversold RSI"
        elif regime is Regime.VOLATILE:
            reason = "volatility filter blocked signal"
        elif score.bias == "NEUTRAL":
            reason = "ensemble confidence below threshold"
        else:
            reason = f"ensemble {score.bias.lower()} signal"
        return SignalResult(score.bias, score.confidence, reason)
