import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from bananatrade import __version__, web_server
from bananatrade.config import Config
from bananatrade.engine.bar_engine import BarEngine
from bananatrade.feeds.binance_feed import BinanceFeed, Candle
from bananatrade.feeds.feed_manager import FeedManager
from bananatrade.ws_broadcaster import WsBroadcaster


def message(*, closed: bool = True, close_time: int = 60_000, close: str = "101.0") -> str:
    return json.dumps({"e": "kline", "s": "BTCUSDT", "k": {"t": 0, "T": close_time, "o": "100.0", "h": "102.0", "l": "99.0", "c": close, "v": "12.5", "x": closed}})


class FakeConnection:
    def __init__(self, messages: list[str | BaseException]) -> None:
        self.messages = list(messages)
        self.closed = False

    async def recv(self) -> str:
        item = self.messages.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


class Client:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, payload: str) -> None:
        self.messages.append(payload)


def make_feed(**kwargs: Any) -> BinanceFeed:
    return BinanceFeed(Config(symbol="BTCUSDT"), BarEngine(), **kwargs)


def test_version_bumped() -> None:
    assert __version__ == "0.2.0"


def test_url_uses_config_symbol() -> None:
    feed = BinanceFeed(Config(symbol="ETHUSDT"), BarEngine())
    assert feed.url == "wss://stream.binance.com:9443/ws/ethusdt@kline_1m"


def test_url_removes_slash() -> None:
    feed = BinanceFeed(Config(symbol="BTC/USDT"), BarEngine())
    assert feed.url.endswith("/btcusdt@kline_1m")


def test_parse_closed_candle() -> None:
    candle = make_feed().parse_message(message())
    assert candle == Candle(60.0, 100.0, 102.0, 99.0, 101.0, 12.5)


def test_parse_incomplete_returns_none() -> None:
    assert make_feed().parse_message(message(closed=False)) is None


def test_parse_bytes() -> None:
    assert make_feed().parse_message(message().encode("utf-8")) is not None


def test_parse_non_object_rejected() -> None:
    with pytest.raises(TypeError, match="object"):
        make_feed().parse_message("[]")


def test_parse_missing_kline_is_none() -> None:
    assert make_feed().parse_message(json.dumps({"e": "ping"})) is None


@pytest.mark.parametrize("field", ["o", "h", "l", "c", "v", "T"])
def test_parse_invalid_numeric_rejected(field: str) -> None:
    payload = json.loads(message())
    payload["k"][field] = "bad"
    with pytest.raises(ValueError, match="numeric"):
        make_feed().parse_message(json.dumps(payload))


def test_parse_non_positive_price_rejected() -> None:
    with pytest.raises(ValueError, match="valid"):
        make_feed().parse_message(message(close="0"))


def test_parse_inconsistent_ohlc_rejected() -> None:
    payload = json.loads(message())
    payload["k"]["h"] = "100.5"
    with pytest.raises(ValueError, match="inconsistent"):
        make_feed().parse_message(json.dumps(payload))


def test_candle_as_dict() -> None:
    candle = Candle(1.0, 2.0, 3.0, 1.5, 2.5, 4.0)
    assert candle.as_dict() == {"timestamp": 1.0, "open": 2.0, "high": 3.0, "low": 1.5, "close": 2.5, "volume": 4.0}


@pytest.mark.asyncio
async def test_closed_candle_reaches_bar_engine() -> None:
    engine = BarEngine()
    feed = BinanceFeed(Config(), engine)
    await feed.consume_message(message())
    assert engine.candles[-1]["close"] == 101.0


@pytest.mark.asyncio
async def test_open_candle_does_not_reach_bar_engine() -> None:
    engine = BarEngine()
    feed = BinanceFeed(Config(), engine)
    await feed.consume_message(message(closed=False))
    assert engine.candles == ()


@pytest.mark.asyncio
async def test_listener_receives_candle() -> None:
    received: list[Candle] = []
    feed = make_feed()
    feed.add_listener(received.append)
    await feed.consume_message(message())
    assert received[0].close == 101.0


@pytest.mark.asyncio
async def test_async_listener_receives_candle() -> None:
    received: list[Candle] = []

    async def listener(candle: Candle) -> None:
        received.append(candle)

    feed = make_feed()
    feed.add_listener(listener)
    await feed.consume_message(message())
    assert len(received) == 1


@pytest.mark.asyncio
async def test_start_calls_configured_connector() -> None:
    calls: list[str] = []

    async def connector(url: str) -> FakeConnection:
        calls.append(url)
        return FakeConnection([message(), asyncio.CancelledError()])

    feed = make_feed(connector=connector)
    with pytest.raises(asyncio.CancelledError):
        await feed.start()
    assert calls == [feed.url]


@pytest.mark.asyncio
async def test_start_reconnects_after_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    async def connector(url: str) -> FakeConnection:
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeConnection([ConnectionError("lost")])
        raise asyncio.CancelledError

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", sleep)
    feed = make_feed(connector=connector)
    with pytest.raises(asyncio.CancelledError):
        await feed.start()
    assert sleeps == [1.0]
    assert feed.disconnect_count == 1


@pytest.mark.asyncio
async def test_backoff_caps_at_sixty(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def connector(url: str) -> FakeConnection:
        raise ConnectionError("down")

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 7:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", sleep)
    feed = make_feed(connector=connector)
    with pytest.raises(asyncio.CancelledError):
        await feed.start()
    assert sleeps[-1] == 60.0


@pytest.mark.asyncio
async def test_stop_clears_running_and_connected() -> None:
    feed = make_feed()
    feed._running = True
    feed._connected = True
    feed.stop()
    assert not feed.running
    assert not feed.connected


def test_max_backoff_is_capped() -> None:
    feed = make_feed(max_backoff=100.0)
    assert feed._max_backoff == 60.0


def test_invalid_max_backoff_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        make_feed(max_backoff=0.0)


@pytest.mark.asyncio
async def test_manager_broadcasts_closed_candle() -> None:
    broadcaster = WsBroadcaster()
    client = Client()
    await broadcaster.register(client)
    feed = BinanceFeed(Config(), BarEngine())
    manager = FeedManager(Config(), broadcaster=broadcaster, feed=feed)
    await feed.consume_message(message())
    assert json.loads(client.messages[0])["type"] == "candle"
    assert json.loads(client.messages[0])["close"] == 101.0
    await manager.stop()


@pytest.mark.asyncio
async def test_manager_listener_runs() -> None:
    received: list[float] = []
    feed = BinanceFeed(Config(), BarEngine())
    manager = FeedManager(Config(), feed=feed)
    manager.add_listener(lambda candle: received.append(candle.close))
    await feed.consume_message(message())
    assert received == [101.0]


@pytest.mark.asyncio
async def test_manager_start_tracks_started_at() -> None:
    async def connector(url: str) -> FakeConnection:
        return FakeConnection([asyncio.CancelledError()])

    manager = FeedManager(Config(), connector=connector)
    with pytest.raises(asyncio.CancelledError):
        await manager.start()
    assert isinstance(manager.started_at, datetime)
    assert manager.started_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_manager_stop_is_idempotent() -> None:
    manager = FeedManager(Config())
    await manager.stop()
    await manager.stop()
    assert not manager.running


def test_manager_initial_state() -> None:
    manager = FeedManager(Config())
    assert not manager.running
    assert not manager.connected
    assert manager.last_candle_at is None


def test_health_state_schema() -> None:
    payload = web_server.health_state()
    assert set(payload) == {"status", "feed_connected", "last_candle_at", "uptime_seconds"}
    assert payload["status"] == "degraded"


def test_health_state_uptime_non_negative() -> None:
    assert web_server.health_state()["uptime_seconds"] >= 0


def test_health_state_last_candle_iso() -> None:
    web_server.FEED_MANAGER.feed._last_candle_at = 60.0
    payload = web_server.health_state()
    assert payload["last_candle_at"] == "1970-01-01T00:01:00+00:00"
    web_server.FEED_MANAGER.feed._last_candle_at = None
