"""Weighted ensemble signal generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from ..data.indicators import rsi
from .regime_detector import Regime, RegimeDetector


@dataclass(frozen=True)
class SignalScore:
    """Directional ensemble score."""

    bias: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float
    components: dict[str, float]


class EnsembleSignal:
    """Combine moving-average crossover, RSI, and regime signals."""

    def __init__(
        self,
        regime_detector: RegimeDetector | None = None,
        ma_fast: int = 20,
        ma_slow: int = 50,
    ) -> None:
        if ma_fast <= 0 or ma_slow <= 0 or ma_fast >= ma_slow:
            raise ValueError("ma_fast and ma_slow must be positive with ma_fast below ma_slow")
        self.regime_detector = regime_detector or RegimeDetector()
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self._last_rsi: float | None = None

    @property
    def last_rsi(self) -> float | None:
        """Return RSI used for most recent score."""
        return self._last_rsi

    def score(self, candles: list[dict[str, object]]) -> SignalScore:
        """Return one gated directional score from candle history."""
        frame = pd.DataFrame(candles)
        components = {"ma_cross_score": 0.0, "rsi_score": 0.0, "regime_multiplier": 0.7}
        if "close" not in frame or len(frame) < self.ma_slow + 1:
            self._last_rsi = None
            return SignalScore("NEUTRAL", 0.0, components)
        close = pd.to_numeric(frame["close"], errors="coerce")
        if close.isna().any():
            self._last_rsi = None
            return SignalScore("NEUTRAL", 0.0, components)
        prepared = self._with_ohlc(frame, close)
        try:
            regime = self.regime_detector.detect(prepared)
        except ValueError:
            self._last_rsi = None
            return SignalScore("NEUTRAL", 0.0, components)
        fast = close.rolling(self.ma_fast, min_periods=self.ma_fast).mean()
        slow = close.rolling(self.ma_slow, min_periods=self.ma_slow).mean()
        previous_fast = float(fast.iloc[-2])
        previous_slow = float(slow.iloc[-2])
        current_fast = float(fast.iloc[-1])
        current_slow = float(slow.iloc[-1])
        bullish_cross = previous_fast <= previous_slow and current_fast > current_slow
        bearish_cross = previous_fast >= previous_slow and current_fast < current_slow
        direction = 1 if bullish_cross else -1 if bearish_cross else 0
        ma_score = 1.0 if direction else 0.0
        current_rsi = float(rsi(close, 14).iloc[-1])
        self._last_rsi = current_rsi
        if direction > 0:
            rsi_score = max(0.0, min(1.0, (70.0 - current_rsi) / 40.0))
        elif direction < 0:
            rsi_score = max(0.0, min(1.0, (current_rsi - 30.0) / 40.0))
        else:
            rsi_score = 0.0
        multiplier = {Regime.TRENDING: 1.0, Regime.RANGING: 0.7, Regime.VOLATILE: 0.3}[regime]
        confidence = max(0.0, min(1.0, 0.6 * ma_score + 0.25 * rsi_score + 0.15 * multiplier))
        bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG" if direction > 0 else "SHORT" if direction < 0 else "NEUTRAL"
        if confidence < 0.65 or regime is Regime.VOLATILE or rsi_score == 0.0:
            bias = "NEUTRAL"
        components = {
            "ma_cross_score": ma_score,
            "rsi_score": rsi_score,
            "regime_multiplier": multiplier,
        }
        return SignalScore(bias, confidence, components)

    @staticmethod
    def _with_ohlc(frame: pd.DataFrame, close: pd.Series) -> list[dict[str, object]]:
        if "high" not in frame:
            frame["high"] = close
        if "low" not in frame:
            frame["low"] = close
        records = frame.to_dict("records")
        return [{str(key): value for key, value in record.items()} for record in records]
