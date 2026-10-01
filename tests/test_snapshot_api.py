import json
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pandas as pd
import pytest

from bananatrade.snapshot_api import (
    SnapshotRequestHandler,
    build_snapshot_response,
    make_snapshot_handler,
)

START = datetime(2025, 1, 1, tzinfo=UTC)


def candles() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp_ms": int((START + timedelta(hours=index)).timestamp() * 1000),
                "open": 100.0 + index,
                "high": 102.0 + index,
                "low": 98.0 + index,
                "close": 101.0 + index,
                "volume": 1000.0 + index,
            }
            for index in range(3)
        ]
    )


def test_snapshot_last_price_equals_candles_last_close_for_same_symbol_and_timeframe() -> None:
    frame = candles()
    response = build_snapshot_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=frame,
        as_of=START + timedelta(hours=3),
    )

    assert response["last_price"] == response["candles"][-1]["close"]
    assert response["last_price"] == float(frame.iloc[-1]["close"])
    assert response["stale"] is False


def test_snapshot_response_uses_last_close_of_requested_timeframe() -> None:
    result = build_snapshot_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=candles(),
        as_of=START + timedelta(hours=3),
    )

    assert result["last_price"] == 103.0
    assert isinstance(result["indicators"], dict)
    assert result["timestamp"] == "2025-01-01T03:00:00Z"
    assert result["as_of"] == "2025-01-01T03:00:00Z"


def test_snapshot_response_marks_fresh_data_at_two_bar_boundary() -> None:
    result = build_snapshot_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=candles(),
        as_of=START + timedelta(hours=5),
    )

    assert result["last_price"] == result["candles"][-1]["close"]
    assert result["stale"] is False


def test_snapshot_response_marks_data_stale_after_two_bars() -> None:
    result = build_snapshot_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=candles(),
        as_of=START + timedelta(hours=5, seconds=1),
    )

    assert result["last_price"] == result["candles"][-1]["close"]
    assert result["stale"] is True


def test_snapshot_response_rejects_when_no_candle_is_closed() -> None:
    with pytest.raises(ValueError, match="No closed candles"):
        build_snapshot_response(
            symbol="BTC/USDT",
            timeframe="1h",
            candles=candles(),
            as_of=START + timedelta(minutes=30),
        )


def test_snapshot_http_endpoint_reads_symbol_and_timeframe_query() -> None:
    server = _start_server(
        make_snapshot_handler(
            {"BTC/USDT": {"1h": candles()}},
            as_of=START + timedelta(hours=3),
        )
    )
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/api/snapshot?symbol=BTC%2FUSDT&timeframe=1h")
        response = connection.getresponse()
        result = response.read().decode("utf-8")
    finally:
        connection.close()
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert result
    payload = json.loads(result)
    assert payload["last_price"] == payload["candles"][-1]["close"]
    assert payload["last_price"] == 103.0
    assert payload["stale"] is False


def test_snapshot_http_endpoint_returns_bad_request_for_missing_query() -> None:
    server = _start_server(
        make_snapshot_handler(
            {"BTC/USDT": {"1h": candles()}},
            as_of=START + timedelta(hours=3),
        )
    )
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/api/snapshot?symbol=BTC%2FUSDT")
        response = connection.getresponse()
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()

    assert response.status == 400


def _start_server(handler: type[SnapshotRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
