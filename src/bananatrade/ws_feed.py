"""WebSocket price feed subscriber with exponential reconnect backoff."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from math import isfinite
from typing import Any, Protocol, cast

LOGGER = logging.getLogger(__name__)

TickHandler = Callable[[dict[str, Any]], None | Awaitable[None]]


class ConnectionSession(Protocol):
    """Protocol for an active WebSocket connection."""

    async def recv(self) -> str | bytes:
        """Receive the next WebSocket frame."""
        ...

    async def close(self) -> None:
        """Close the WebSocket connection."""
        ...


ConnectorCallable = Callable[[str], Awaitable[ConnectionSession]]


class FeedConnectionError(RuntimeError):
    """Exception raised when feed connection fails."""


class WsFeed:
    """Subscribe to a WebSocket price feed and buffer ticks."""

    def __init__(
        self,
        max_ticks: int = 200,
        *,
        connector: ConnectorCallable | None = None,
        max_backoff: float = 30.0,
    ) -> None:
        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        self._ticks: deque[dict[str, Any]] = deque(maxlen=max_ticks)
        self._listeners: list[TickHandler] = []
        self._connector = connector
        self._max_backoff = min(max_backoff, 30.0)
        self._running = False
        self._disconnect_count = 0

    @property
    def ticks(self) -> tuple[dict[str, Any], ...]:
        """Return buffered ticks in chronological order."""
        return tuple(self._ticks)

    @property
    def disconnect_count(self) -> int:
        """Return total connection failures encountered."""
        return self._disconnect_count

    def add_listener(self, listener: TickHandler) -> None:
        """Register a callback invoked when a valid tick arrives."""
        self._listeners.append(listener)

    def on_message(self, msg: str | bytes) -> dict[str, Any] | None:
        """Parse and store one tick message, notifying registered listeners."""
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8")
        if not isinstance(msg, str):
            raise TypeError("msg must be str or bytes")
        data = json.loads(msg)
        if not isinstance(data, dict):
            raise TypeError("tick message must be a JSON object")
        for required in ("symbol", "price", "timestamp"):
            if required not in data:
                raise KeyError(f"tick message missing {required}")
        symbol = str(data["symbol"]).strip()
        price = float(data["price"])
        timestamp = float(data["timestamp"])
        if not symbol or not isfinite(price) or not isfinite(timestamp) or price <= 0 or timestamp <= 0:
            raise ValueError("invalid symbol, price, or timestamp")
        tick_data: dict[str, Any] = {
            "symbol": symbol,
            "price": price,
            "timestamp": timestamp,
        }
        self._ticks.append(tick_data)
        for listener in self._listeners:
            result = listener(dict(tick_data))
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(result)
                else:
                    loop.create_task(result)
        return dict(tick_data)

    async def connect(self, url: str) -> None:
        """Connect to the WebSocket feed and reconnect with exponential backoff."""
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
        self._running = True
        backoff = 1.0
        while self._running:
            try:
                connector = self._connector or self._default_connector
                connection = await connector(url)
                backoff = 1.0
                while self._running:
                    msg = await connection.recv()
                    self.on_message(msg)
            except asyncio.CancelledError:
                self._running = False
                raise
            except (ConnectionError, OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
                if not self._running:
                    break
                self._disconnect_count += 1
                LOGGER.warning("ws_feed connection failure (#%d): %s", self._disconnect_count, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, self._max_backoff)

    async def _default_connector(self, url: str) -> ConnectionSession:
        """Open a connection through optional ``websockets`` dependency."""
        module = importlib.import_module("websockets")
        connect = getattr(module, "connect", None)
        if not callable(connect):
            raise FeedConnectionError("websockets.connect is unavailable")
        connection = await connect(url)
        return cast(ConnectionSession, connection)

    def stop(self) -> None:
        """Stop the reconnect loop."""
        self._running = False
