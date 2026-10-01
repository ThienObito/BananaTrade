"""WebSocket client broadcaster for paper-market updates."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)


class WebSocketClient(Protocol):
    """Minimal async WebSocket protocol used by the broadcaster."""

    async def send(self, payload: str) -> None:
        """Send one text frame."""
        ...


class StdlibWebSocket:
    """Thread-safe WebSocket client wrapper over stdlib socket stream."""

    def __init__(self, wfile: Any) -> None:
        self.wfile = wfile
        self._lock = threading.Lock()

    def send_json(self, data: dict[str, Any]) -> None:
        """Encode and send one text frame over the connection."""
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.append(126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(127)
            header.extend(length.to_bytes(8, "big"))
        with self._lock:
            self.wfile.write(bytes(header) + payload)
            self.wfile.flush()

    async def send(self, payload: str) -> None:
        """Send one string frame asynchronously."""
        data = json.loads(payload)
        if isinstance(data, dict):
            self.send_json(data)


class WsBroadcaster:
    """Broadcast JSON-serializable dictionaries to connected clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocketClient] = set()
        self._lock = asyncio.Lock()

    @property
    def clients(self) -> tuple[WebSocketClient, ...]:
        """Return a snapshot of registered clients."""
        return tuple(self._clients)

    async def register(self, ws: WebSocketClient) -> None:
        """Register one WebSocket client."""
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws: WebSocketClient) -> None:
        """Remove one WebSocket client if present."""
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, data: dict[str, Any]) -> int:
        """Send JSON data to all clients and remove failed connections."""
        payload = json.dumps(data, separators=(",", ":"))
        async with self._lock:
            clients = tuple(self._clients)
        results = await asyncio.gather(
            *(self._send_one(client, payload) for client in clients),
            return_exceptions=False,
        )
        return sum(1 for result in results if result)

    async def _send_one(self, client: WebSocketClient, payload: str) -> bool:
        try:
            await client.send(payload)
            return True
        except (ConnectionError, OSError, RuntimeError) as exc:
            LOGGER.debug("removing disconnected WebSocket client: %s", exc)
            await self.unregister(client)
            return False


class FeedBroadcaster:
    """Forward accepted feed ticks to browser WebSocket clients."""

    def __init__(self, broadcaster: WsBroadcaster) -> None:
        self.broadcaster = broadcaster

    def handler(self) -> Callable[[dict[str, Any]], Awaitable[None]]:
        """Return async tick listener suitable for ``WsFeed.add_listener``."""

        async def publish(tick: dict[str, Any]) -> None:
            await self.broadcaster.broadcast(tick)

        return publish
