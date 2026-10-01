import asyncio
import json
from typing import Any

import pytest

from bananatrade.engine.bar_engine import BarEngine
from bananatrade.ws_broadcaster import WsBroadcaster
from bananatrade.ws_feed import WsFeed


class FakeClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.messages: list[str] = []
        self.fail = fail

    async def send(self, payload: str) -> None:
        if self.fail:
            raise ConnectionError("closed")
        self.messages.append(payload)


class FakeConnection:
    def __init__(self, messages: list[str | BaseException]) -> None:
        self.messages = list(messages)

    async def recv(self) -> str:
        item = self.messages.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        return None


def tick(symbol: str = "BTC/USDT", price: float = 100.0, timestamp: float = 1.0) -> str:
    return json.dumps({"symbol": symbol, "price": price, "timestamp": timestamp})


def test_ws_feed_parses_and_stores_tick() -> None:
    feed = WsFeed()

    parsed = feed.on_message(tick(price=101.5, timestamp=10.0))

    assert parsed == {"symbol": "BTC/USDT", "price": 101.5, "timestamp": 10.0}
    assert feed.ticks == (parsed,)


def test_ws_feed_keeps_only_last_200_ticks() -> None:
    feed = WsFeed()

    for index in range(205):
        feed.on_message(tick(price=100 + index, timestamp=index + 1))

    assert len(feed.ticks) == 200
    assert feed.ticks[0]["price"] == 105.0


def test_ws_feed_rejects_missing_symbol() -> None:
    feed = WsFeed()

    with pytest.raises(KeyError, match="symbol"):
        feed.on_message(json.dumps({"price": 100, "timestamp": 1}))


def test_ws_feed_rejects_non_positive_price() -> None:
    feed = WsFeed()

    with pytest.raises(ValueError, match="invalid"):
        feed.on_message(tick(price=0))


@pytest.mark.asyncio
async def test_ws_feed_calls_async_listener() -> None:
    feed = WsFeed()
    received: list[dict[str, Any]] = []

    async def listener(data: dict[str, Any]) -> None:
        received.append(data)

    feed.add_listener(listener)
    feed.on_message(tick())
    await asyncio.sleep(0)

    assert received[0]["symbol"] == "BTC/USDT"


@pytest.mark.asyncio
async def test_ws_feed_reconnects_after_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    connections = [FakeConnection([ConnectionError("lost")]), FakeConnection([tick(price=102)])]
    calls = 0
    sleeps: list[float] = []

    async def connector(url: str) -> FakeConnection:
        nonlocal calls
        calls += 1
        if calls > len(connections):
            raise asyncio.CancelledError
        return connections[calls - 1]

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) >= 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    feed = WsFeed(connector=connector)

    with pytest.raises(asyncio.CancelledError):
        await feed.connect("ws://localhost:8765")

    assert calls == 1
    assert sleeps == [1.0]
    assert feed.disconnect_count == 1


@pytest.mark.asyncio
async def test_ws_feed_backoff_doubles_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    async def connector(url: str) -> FakeConnection:
        nonlocal calls
        calls += 1
        raise ConnectionError("down")

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    feed = WsFeed(connector=connector)

    with pytest.raises(asyncio.CancelledError):
        await feed.connect("ws://localhost:8765")

    assert sleeps == [1.0, 2.0, 4.0, 8.0]
    assert calls == 4


@pytest.mark.asyncio
async def test_ws_feed_stop_ends_reconnect_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def connector(url: str) -> FakeConnection:
        raise ConnectionError("down")

    async def fake_sleep(delay: float) -> None:
        feed.stop()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    feed = WsFeed(connector=connector)

    await feed.connect("ws://localhost:8765")

    assert feed.disconnect_count == 1


@pytest.mark.asyncio
async def test_broadcaster_register_unregister() -> None:
    broadcaster = WsBroadcaster()
    client = FakeClient()

    await broadcaster.register(client)
    await broadcaster.unregister(client)

    assert broadcaster.clients == ()


@pytest.mark.asyncio
async def test_broadcaster_register_is_idempotent() -> None:
    broadcaster = WsBroadcaster()
    client = FakeClient()

    await broadcaster.register(client)
    await broadcaster.register(client)

    assert broadcaster.clients == (client,)


@pytest.mark.asyncio
async def test_broadcaster_broadcasts_json_to_all_clients() -> None:
    broadcaster = WsBroadcaster()
    first = FakeClient()
    second = FakeClient()
    await broadcaster.register(first)
    await broadcaster.register(second)

    count = await broadcaster.broadcast({"symbol": "BTC/USDT", "price": 100.0})

    assert count == 2
    assert json.loads(first.messages[0])["price"] == 100.0
    assert json.loads(second.messages[0])["symbol"] == "BTC/USDT"


@pytest.mark.asyncio
async def test_broadcaster_removes_failed_client() -> None:
    broadcaster = WsBroadcaster()
    good = FakeClient()
    bad = FakeClient(fail=True)
    await broadcaster.register(good)
    await broadcaster.register(bad)

    count = await broadcaster.broadcast({"price": 100.0})

    assert count == 1
    assert bad not in broadcaster.clients
    assert good in broadcaster.clients


@pytest.mark.asyncio
async def test_broadcaster_empty_broadcast() -> None:
    assert await WsBroadcaster().broadcast({"price": 100.0}) == 0


def test_bar_engine_feed_tick_forms_one_minute_candle() -> None:
    engine = BarEngine()
    completed: list[dict[str, object]] = []
    engine.add_listener(completed.append)

    engine.feed_tick(100.0, 0.0)
    engine.feed_tick(105.0, 10.0)
    engine.feed_tick(98.0, 59.0)
    engine.feed_tick(102.0, 60.0)

    assert completed == [{
        "timestamp": 0.0,
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 98.0,
        "volume": 3.0,
    }]
    assert engine.candles[0]["close"] == 98.0


def test_bar_engine_feed_tick_starts_next_candle() -> None:
    engine = BarEngine()

    engine.feed_tick(100.0, 60.0)
    engine.feed_tick(110.0, 120.0)

    assert engine.candles[0]["open"] == 100.0
    assert engine.candles[0]["timestamp"] == 60.0


def test_bar_engine_feed_tick_rejects_out_of_order() -> None:
    engine = BarEngine()
    engine.feed_tick(100.0, 60.0)

    with pytest.raises(ValueError, match="chronological"):
        engine.feed_tick(99.0, 59.0)


def test_bar_engine_feed_tick_rejects_invalid_price() -> None:
    with pytest.raises(ValueError, match="price"):
        BarEngine().feed_tick(0.0, 1.0)


def test_web_server_websocket_route_exists() -> None:
    from bananatrade.web_server import Handler

    assert Handler.websocket_route == "/ws"


def test_web_server_websocket_route_is_upgrade_marker() -> None:
    from bananatrade.web_server import Handler

    assert Handler.websocket_route.startswith("/")


@pytest.mark.asyncio
async def test_feed_listener_can_forward_to_broadcaster() -> None:
    feed = WsFeed()
    broadcaster = WsBroadcaster()
    client = FakeClient()
    await broadcaster.register(client)

    async def listener(data: dict[str, Any]) -> None:
        await broadcaster.broadcast(data)

    feed.add_listener(listener)
    feed.on_message(tick(price=103.0))
    await asyncio.sleep(0.01)

    assert json.loads(client.messages[0])["price"] == 103.0
