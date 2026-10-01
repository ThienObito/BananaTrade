"""Lifecycle coordination for paper market-data feeds."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from ..config import Config
from ..engine.bar_engine import BarEngine
from ..ws_broadcaster import WsBroadcaster
from .binance_feed import BinanceFeed, Candle, Connector


class FeedManager:
    """Start, stop, and broadcast closed candles from BinanceFeed."""

    def __init__(
        self,
        config: Config,
        bar_engine: BarEngine | None = None,
        broadcaster: WsBroadcaster | None = None,
        *,
        connector: Connector | None = None,
        feed: BinanceFeed | None = None,
    ) -> None:
        self.config = config
        self.bar_engine = bar_engine or BarEngine()
        self.broadcaster = broadcaster or WsBroadcaster()
        self.feed = feed or BinanceFeed(config, self.bar_engine, connector=connector)
        self._task: asyncio.Task[None] | None = None
        self._started_at: datetime | None = None
        self._listeners: list[Callable[[Candle], None | Awaitable[None]]] = []
        self.feed.add_listener(self._on_candle)

    @property
    def running(self) -> bool:
        """Return whether manager has an active feed task."""
        return self._task is not None and not self._task.done()

    @property
    def connected(self) -> bool:
        """Return current WebSocket connection state."""
        return self.feed.connected

    @property
    def last_candle_at(self) -> float | None:
        """Return latest closed candle timestamp."""
        return self.feed.last_candle_at

    @property
    def started_at(self) -> datetime | None:
        """Return manager start time."""
        return self._started_at

    def add_listener(self, listener: Callable[[Candle], None | Awaitable[None]]) -> None:
        """Register candle listener."""
        self._listeners.append(listener)

    async def start(self) -> None:
        """Run feed lifecycle until feed stops or task is cancelled."""
        if self.running:
            return
        self._started_at = datetime.now(UTC)
        self._task = asyncio.current_task()
        try:
            await self.feed.start()
        finally:
            self._task = None

    async def run(self) -> None:
        """Alias for start used by asyncio task orchestration."""
        await self.start()

    async def stop(self) -> None:
        """Stop feed and await its owned task when needed."""
        self.feed.stop()
        task = self._task
        current = asyncio.current_task()
        if task is not None and task is not current:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._task = None

    async def _on_candle(self, candle: Candle) -> None:
        payload: dict[str, Any] = {"type": "candle", "symbol": self.config.symbol, **candle.as_dict()}
        await self.broadcaster.broadcast(payload)
        for listener in tuple(self._listeners):
            result = listener(candle)
            if asyncio.iscoroutine(result):
                await result
