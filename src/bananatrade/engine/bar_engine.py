"""MQL5-style closed-bar dispatcher for paper trading."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from math import isfinite
from typing import Any


class BarEngine:
    """Store recent candles and dispatch each accepted bar to listeners."""

    def __init__(self, max_candles: int = 50) -> None:
        if max_candles <= 0:
            raise ValueError("max_candles must be positive")
        self._candles: deque[dict[str, Any]] = deque(maxlen=max_candles)
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._active_minute: int | None = None
        self._active_candle: dict[str, Any] | None = None

    @property
    def candles(self) -> tuple[dict[str, Any], ...]:
        """Return recent candles in chronological order."""
        return tuple(self._candles)

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """Register one callback invoked after each bar is stored."""
        self._listeners.append(listener)

    def feed_tick(self, price: float, timestamp: float) -> None:
        """Aggregate ticks into one-minute OHLCV candles."""
        if not isfinite(price) or price <= 0:
            raise ValueError("price must be positive and finite")
        if not isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be finite and non-negative")
        minute = int(timestamp // 60)
        if self._active_minute is None:
            self._active_minute = minute
            self._active_candle = self._new_tick_candle(price, float(minute * 60))
            return
        if minute < self._active_minute:
            raise ValueError("ticks must arrive in chronological order")
        if minute == self._active_minute:
            if self._active_candle is None:
                raise RuntimeError("active candle is missing")
            self._active_candle["high"] = max(float(self._active_candle["high"]), price)
            self._active_candle["low"] = min(float(self._active_candle["low"]), price)
            self._active_candle["close"] = price
            self._active_candle["volume"] = float(self._active_candle["volume"]) + 1.0
            return
        if self._active_candle is not None:
            self.on_bar(self._active_candle)
        self._active_minute = minute
        self._active_candle = self._new_tick_candle(price, float(minute * 60))

    @staticmethod
    def _new_tick_candle(price: float, timestamp: float) -> dict[str, Any]:
        return {
            "timestamp": timestamp,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1.0,
        }

    def on_bar(self, candle: Mapping[str, Any]) -> None:
        """Store one candle and dispatch a detached dictionary to listeners."""
        if not isinstance(candle, Mapping):
            raise TypeError("candle must be a mapping")
        stored = dict(candle)
        self._candles.append(stored)
        for listener in self._listeners:
            listener(dict(stored))
