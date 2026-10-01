import json
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pandas as pd
import pytest

from bananatrade.signal_api import (
    SignalRequestHandler,
    build_signal_response,
    make_signal_handler,
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
            for index in range(5)
        ]
    )


def test_signal_response_returns_schema_and_bounded_confidence() -> None:
    result = build_signal_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=candles(),
        as_of=START + timedelta(hours=5),
        bias="LONG",
        confidence=0.75,
    )

    assert set(result) == {"symbol", "bias", "confidence", "as_of", "stale"}
    assert result["symbol"] == "BTC/USDT"
    assert result["bias"] == "LONG"
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["stale"] is False


def test_signal_response_marks_signal_stale_after_three_bars() -> None:
    result = build_signal_response(
        symbol="BTC/USDT",
        timeframe="1h",
        candles=candles(),
        as_of=START + timedelta(hours=8, seconds=1),
        bias="SHORT",
        confidence=0.25,
    )

    assert result["stale"] is True
    assert result["bias"] == "SHORT"


def test_signal_response_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        build_signal_response(
            symbol="BTC/USDT",
            timeframe="1h",
            candles=candles(),
            as_of=START + timedelta(hours=5),
            bias="NEUTRAL",
            confidence=1.1,
        )


def test_signal_http_endpoint_returns_schema() -> None:
    server = _start_server(
        make_signal_handler(
            {"BTC/USDT": {"1h": candles()}},
            as_of=START + timedelta(hours=5),
            bias="LONG",
            confidence=0.8,
        )
    )
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/api/signal?symbol=BTC%2FUSDT&timeframe=1h")
        response = connection.getresponse()
        result = response.read().decode("utf-8")
    finally:
        connection.close()
        server.shutdown()
        server.server_close()

    payload = json.loads(result)
    assert response.status == 200
    assert set(payload) == {"symbol", "bias", "confidence", "as_of", "stale"}
    assert payload["symbol"] == "BTC/USDT"
    assert payload["bias"] == "LONG"
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["stale"] is False


def _start_server(handler: type[SignalRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
