from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from bananatrade import web_server
from bananatrade.paper_broker import PaperBroker
from bananatrade.runtime import RuntimeService


class UnexpectedPostFailure(Exception):
    """Failure used to verify that the server hides unexpected exceptions."""


class UnexpectedAnalysisFailure(Exception):
    """Failure used to verify that analysis failures return JSON."""


@contextmanager
def running_server() -> Iterator[tuple[str, int]]:
    server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        server_address = server.server_address
        assert isinstance(server_address, tuple)
        host = server_address[0]
        port = server_address[1]
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, str | None, dict[str, Any]]:
    connection = http.client.HTTPConnection(host, port, timeout=5)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read().decode("utf-8")
        decoded = json.loads(response_body)
        assert isinstance(decoded, dict)
        return response.status, response.getheader("Content-Type"), decoded
    finally:
        connection.close()


def test_known_order_error_returns_specific_json_status_and_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    with running_server() as (host, port):
        status, content_type, body = request_json(
            host,
            port,
            "POST",
            "/api/paper/order",
            {"symbol": "BTC/USDT", "side": "BUY", "qty": -1, "price": 100},
        )

    assert status == 400
    assert content_type == "application/json"
    assert body == {"error": "qty must be greater than 0"}


def test_unexpected_order_error_returns_json_500_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    def fail_record_fill(fill: object) -> None:
        raise UnexpectedPostFailure("private failure details")

    with patch.object(web_server, "record_fill", side_effect=fail_record_fill), running_server() as (
        host,
        port,
    ):
        status, content_type, body = request_json(
            host,
            port,
            "POST",
            "/api/paper/order",
            {"symbol": "BTC/USDT", "side": "BUY", "qty": 1, "price": 100},
        )

    assert status == 500
    assert content_type == "application/json"
    assert body == {"error": "Internal server error"}
    assert "traceback" not in json.dumps(body).lower()
    assert "private failure details" not in json.dumps(body)


def test_unexpected_analysis_error_returns_json_500_without_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_init(self: RuntimeService, root: Path, db_path: Path, gateway: object | None = None) -> None:
        return None

    async def fail_analysis(self: RuntimeService, symbol: str) -> dict[str, object]:
        raise UnexpectedAnalysisFailure("analysis traceback details")

    monkeypatch.setattr(RuntimeService, "__init__", no_init)
    monkeypatch.setattr(RuntimeService, "run", fail_analysis)

    with running_server() as (host, port):
        status, content_type, body = request_json(host, port, "GET", "/api/analysis/run")

    assert status == 500
    assert content_type == "application/json"
    assert body == {"error": "Internal server error"}
    assert "traceback" not in json.dumps(body).lower()
    assert "analysis traceback details" not in json.dumps(body)


def test_known_analysis_error_returns_specific_json_status_and_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_init(self: RuntimeService, root: Path, db_path: Path, gateway: object | None = None) -> None:
        return None

    async def fail_analysis(self: RuntimeService, symbol: str) -> dict[str, object]:
        raise RuntimeError("analysis unavailable")

    monkeypatch.setattr(RuntimeService, "__init__", no_init)
    monkeypatch.setattr(RuntimeService, "run", fail_analysis)

    with running_server() as (host, port):
        status, content_type, body = request_json(host, port, "GET", "/api/analysis/run")

    assert status == 503
    assert content_type == "application/json"
    assert body == {"error": "analysis unavailable"}


def test_paper_state_endpoint_returns_cash_positions_and_open_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    with running_server() as (host, port):
        status, content_type, body = request_json(host, port, "GET", "/api/paper/state")

    assert status == 200
    assert content_type == "application/json"
    assert set(body) == {"cash", "positions", "open_orders"}
    assert body["cash"] == 1_000.0
    assert body["positions"] == []
    assert body["open_orders"] == []


def test_paper_order_accepts_buy_and_returns_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    with running_server() as (host, port):
        status, content_type, body = request_json(
            host,
            port,
            "POST",
            "/api/paper/order",
            {"symbol": "BTC/USDT", "side": "BUY", "qty": 2.0, "price": 100.0},
        )

    assert status == 200
    assert content_type == "application/json"
    assert body["order"]["side"] == "BUY"
    assert body["order"]["quantity"] == 2.0


@pytest.mark.parametrize(
    ("name", "payload", "message"),
    [
        ("symbol", {"symbol": "", "side": "BUY", "qty": 1.0, "price": 100.0}, "symbol"),
        ("side", {"symbol": "BTC/USDT", "side": "HOLD", "qty": 1.0, "price": 100.0}, "side"),
        ("qty", {"symbol": "BTC/USDT", "side": "BUY", "qty": 0, "price": 100.0}, "qty"),
        ("price", {"symbol": "BTC/USDT", "side": "BUY", "qty": 1.0, "price": 0}, "price"),
    ],
)
def test_paper_order_rejects_each_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    payload: dict[str, object],
    message: str,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    with running_server() as (host, port):
        status, content_type, body = request_json(host, port, "POST", "/api/paper/order", payload)

    assert status == 400, name
    assert content_type == "application/json"
    assert message in body["error"]


def test_signal_web_endpoint_returns_schema_and_freshness() -> None:
    with running_server() as (host, port):
        status, content_type, body = request_json(
            host,
            port,
            "GET",
            "/api/signal?symbol=BTC%2FUSDT&timeframe=1h",
        )

    assert status == 200
    assert content_type == "application/json"
    assert set(body) == {"symbol", "bias", "confidence", "as_of", "stale"}
    assert body["symbol"] == "BTC/USDT"
    assert body["bias"] in {"LONG", "SHORT", "NEUTRAL"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["stale"] is False


def test_snapshot_web_endpoint_last_price_matches_candles_endpoint() -> None:
    with running_server() as (host, port):
        snapshot_status, snapshot_type, snapshot = request_json(
            host,
            port,
            "GET",
            "/api/snapshot?symbol=BTC%2FUSDT&timeframe=1h",
        )
        candles_status, candles_type, candles = request_json(
            host,
            port,
            "GET",
            "/api/candles?symbol=BTC%2FUSDT&timeframe=1h",
        )

    assert snapshot_status == 200
    assert candles_status == 200
    assert snapshot_type == "application/json"
    assert candles_type == "application/json"
    assert isinstance(snapshot["stale"], bool)
    assert snapshot["last_price"] == candles["candles"][-1]["close"]
    assert snapshot["last_price"] == snapshot["candles"][-1]["close"]


def test_snapshot_web_endpoint_rejects_other_symbol_or_timeframe() -> None:
    with running_server() as (host, port):
        status, _, body = request_json(
            host,
            port,
            "GET",
            "/api/snapshot?symbol=ETH%2FUSDT&timeframe=1h",
        )

    assert status == 404
    assert body == {"error": "snapshot data not found"}


def test_snapshot_unknown_symbol_returns_json_error() -> None:
    with running_server() as (host, port):
        status, content_type, body = request_json(
            host,
            port,
            "GET",
            "/api/snapshot?symbol=UNKNOWN%2FUSDT&timeframe=1h",
        )

    assert status == 404
    assert content_type == "application/json"
    assert "error" in body


def test_paper_order_missing_body_returns_json_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))

    with running_server() as (host, port):
        status, content_type, body = request_json(host, port, "POST", "/api/paper/order")

    assert status == 400
    assert content_type == "application/json"
    assert "error" in body


def test_analysis_api_returns_only_supported_bias_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_init(self: RuntimeService, root: Path, db_path: Path, gateway: object | None = None) -> None:
        return None

    async def fake_analysis(self: RuntimeService, symbol: str) -> dict[str, object]:
        return {
            "reports": [
                {"agent": "invalid", "bias": "NEUTRAL" + chr(43)},
                {"agent": "valid", "bias": "LONG"},
            ]
        }

    monkeypatch.setattr(RuntimeService, "__init__", no_init)
    monkeypatch.setattr(RuntimeService, "run", fake_analysis)

    with running_server() as (host, port):
        status, _, body = request_json(host, port, "GET", "/api/analysis/run")

    reports = body["reports"]
    assert status == 200
    assert isinstance(reports, list)
    assert {report["bias"] for report in reports} <= {"LONG", "SHORT", "NEUTRAL"}
    assert reports[0]["bias"] == "NEUTRAL"

