"""Multi-timeframe signal confirmation."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from .strategy import SignalResult


class MultiTimeframeSignal:
    """Require aligned directional signals on 1-minute and 5-minute bars."""

    def __init__(self, strategy: object | None = None, min_confidence: float = 0.60) -> None:
        self.strategy = strategy
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        self.min_confidence = min_confidence

    def confirm(
        self,
        candles_1m: Sequence[dict[str, object]],
        candles_5m: Sequence[dict[str, object]] | None = None,
    ) -> bool:
        """Return true only when both timeframe signals agree with confidence."""
        one_minute = [dict(candle) for candle in candles_1m]
        five_minute = [dict(candle) for candle in candles_5m] if candles_5m is not None else self.resample(one_minute)
        first = self._signal(one_minute)
        second = self._signal(five_minute)
        return (
            first.bias in {"LONG", "SHORT"}
            and first.bias == second.bias
            and first.confidence >= self.min_confidence
            and second.confidence >= self.min_confidence
        )

    @staticmethod
    def resample(candles_1m: Sequence[dict[str, object]]) -> list[dict[str, object]]:
        """Aggregate consecutive 1-minute candles into five-minute OHLCV bars."""
        if not candles_1m:
            return []
        frame = pd.DataFrame(candles_1m)
        required = {"open", "high", "low", "close"}
        if not required.issubset(frame.columns):
            return []
        groups = [index // 5 for index in range(len(frame))]
        rows: list[dict[str, object]] = []
        for _, group in frame.groupby(groups):
            row: dict[str, object] = {
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
            if "volume" in group:
                row["volume"] = float(pd.to_numeric(group["volume"], errors="coerce").fillna(0).sum())
            rows.append(row)
        return rows

    def _signal(self, candles: list[dict[str, object]]) -> SignalResult:
        strategy = self.strategy
        if strategy is None:
            from .strategy import MACrossStrategy

            strategy = MACrossStrategy()
        generate_signal = getattr(strategy, "generate_signal", None)
        if not callable(generate_signal):
            raise TypeError("strategy must provide generate_signal")
        result = generate_signal(candles)
        if not isinstance(result, SignalResult):
            raise TypeError("strategy must return SignalResult")
        return result
