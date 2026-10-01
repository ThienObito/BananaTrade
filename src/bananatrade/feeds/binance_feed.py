"""Binance public one-minute closed-candle WebSocket feed."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import isfinite
from typing import Protocol, cast

from ..config import Config
from ..engine.bar_engine import BarEngine

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candle:
    """Closed OHLCV candle received from Binance."""

    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self) -> dict[str, float]:
        """Return candle data accepted by BarEngine and JSON clients."""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class BinanceConnection(Protocol):
    """Minimal async connection contract used by BinanceFeed."""

    async def recv(self) -> str | bytes:
        """Receive one WebSocket message."""
        ...

    async def close(self) -> None:
        """Close connection."""
        ...


Connector = Callable[[str], Awaitable[BinanceConnection]]
CandleListener = Callable[[Candle], None | Awaitable[None]]


class BinanceFeed:
    """Consume Binance public kline data and dispatch closed candles."""

    def __init__(
        self,
        config: Config,
        bar_engine: BarEngine,
        *,
        connector: Connector | None = None,
        max_backoff: float = 60.0,
    ) -> None:
        if max_backoff <= 0:
            raise ValueError("max_backoff must be positive")
        self.config = config
        self.bar_engine = bar_engine
        self._connector = connector
        self._max_backoff = min(float(max_backoff), 60.0)
        self._listeners: list[CandleListener] = []
        self._running = False
        self._connected = False
        self._last_candle_at: float | None = None
        self._disconnect_count = 0

    @property
    def url(self) -> str:
        """Return Binance public kline stream URL."""
        symbol = self.config.symbol.replace("/", "").lower()
        return f"wss://stream.binance.com:9443/ws/{symbol}@kline_1m"

    @property
    def connected(self) -> bool:
        """Return whether an active WebSocket session is receiving data."""
        return self._connected

    @property
    def running(self) -> bool:
        """Return whether lifecycle loop is active."""
        return self._running

    @property
    def last_candle_at(self) -> float | None:
        """Return latest closed-candle event timestamp."""
        return self._last_candle_at

    @property
    def disconnect_count(self) -> int:
        """Return reconnect failures."""
        return self._disconnect_count

    def add_listener(self, listener: CandleListener) -> None:
        """Register listener invoked after each closed candle."""
        self._listeners.append(listener)

    def stop(self) -> None:
        """Request lifecycle loop shutdown."""
        self._running = False
        self._connected = False

    def parse_message(self, message: str | bytes) -> Candle | None:
        """Parse one Binance kline event; ignore non-closed candles."""
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        if not isinstance(message, str):
            raise TypeError("message must be str or bytes")
        payload = json.loads(message)
        if not isinstance(payload, dict):
            raise TypeError("Binance message must be an object")
        kline = payload.get("k")
        if not isinstance(kline, dict):
            return None
        if kline.get("x") is not True:
            return None
        values = {
            "timestamp": self._number(kline.get("T"), "close timestamp") / 1000.0,
            "open": self._number(kline.get("o"), "open"),
            "high": self._number(kline.get("h"), "high"),
            "low": self._number(kline.get("l"), "low"),
            "close": self._number(kline.get("c"), "close"),
            "volume": self._number(kline.get("v"), "volume"),
        }
        if values["timestamp"] <= 0 or values["open"] <= 0 or values["high"] <= 0 or values["low"] <= 0 or values["close"] <= 0 or values["volume"] < 0:
            raise ValueError("Binance kline values must be valid")
        if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]):
            raise ValueError("Binance kline OHLC values are inconsistent")
        return Candle(**values)

    async def consume_message(self, message: str | bytes) -> Candle | None:
        """Parse and dispatch one message."""
        candle = self.parse_message(message)
        if candle is None:
            return None
        self.bar_engine.on_bar(candle.as_dict())
        self._last_candle_at = candle.timestamp
        for listener in tuple(self._listeners):
            result = listener(candle)
            if asyncio.iscoroutine(result):
                await result
        return candle

    async def start(self) -> None:
        """Connect and reconnect until stopped, using capped exponential backoff."""
        self._running = True
        backoff = 1.0
        while self._running:
            connection: BinanceConnection | None = None
            try:
                connector = self._connector or self._default_connector
                connection = await connector(self.url)
                self._connected = True
                backoff = 1.0
                while self._running:
                    await self.consume_message(await connection.recv())
            except asyncio.CancelledError:
                self.stop()
                raise
            except (ConnectionError, OSError, RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                if not self._running:
                    break
                self._disconnect_count += 1
                LOGGER.warning("binance feed connection failure (#%d): %s", self._disconnect_count, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, self._max_backoff)
            finally:
                self._connected = False
                if connection is not None:
                    try:
                        await connection.close()
                    except (ConnectionError, OSError, RuntimeError) as exc:
                        LOGGER.debug("binance feed close failure: %s", exc)

    async def _default_connector(self, url: str) -> BinanceConnection:
        module = importlib.import_module("websockets")
        connect = getattr(module, "connect", None)
        if not callable(connect):
            raise TypeError("websockets.connect is unavailable")
        return cast(BinanceConnection, await connect(url))

    @staticmethod
    def _number(value: object, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TypeError(f"{field} must be numeric")
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be numeric") from exc
        if not isfinite(result):
            raise ValueError(f"{field} must be finite")
        return result
