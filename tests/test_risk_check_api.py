"""Contract tests for the paper-trading risk-check API."""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from bananatrade.risk import RiskConfig
from bananatrade.risk_check_api import (
    RiskCheckRequestHandler,
    check_risk,
    make_risk_check_handler,
)


def request_payload(**overrides: float) -> dict[str, float]:
    payload = {
        "equity": 10_000.0,
        "entry": 100.0,
        "stop_loss": 99.0,
        "take_profit": 103.0,
        "size": 5.0,
    }
    payload.update(overrides)
    return payload


def test_approved_case_returns_requested_size_and_empty_reasons() -> None:
    result = check_risk(request_payload())

    assert result["approved"] is True
    assert result["reasons"] == []
    assert result["adjusted_size"] == pytest.approx(5.0)


def test_wide_stop_adjusts_size_to_one_percent_equity_and_max_position() -> None:
    result = check_risk(
        request_payload(stop_loss=50.0, take_profit=200.0, size=100.0),
        config=RiskConfig(max_position_pct=0.10),
    )

    # A 50-point stop permits 10000 * 1% / 50 = 2 units.
    # The configured position cap permits 10000 * 10% / 100 = 10 units.
    assert result["approved"] is True
    assert result["adjusted_size"] == pytest.approx(2.0)
    assert result["reasons"] == [
        "size adjusted to limit stop-out risk",
        "size adjusted to configured maximum",
    ]


def test_low_reward_risk_is_rejected() -> None:
    result = check_risk(request_payload(take_profit=100.5))

    assert result["approved"] is False
    assert result["adjusted_size"] == pytest.approx(0.0)
    assert result["reasons"] == ["minimum reward/risk not met"]


def test_http_post_risk_check_returns_json() -> None:
    handler = make_risk_check_handler(RiskConfig())
    server = _start_server(handler)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        body = json.dumps(request_payload()).encode("utf-8")
        connection.request(
            "POST",
            "/api/risk/check",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        result = json.loads(response.read())
    finally:
        connection.close()
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert result["approved"] is True
    assert result["adjusted_size"] == pytest.approx(5.0)


def _start_server(handler: type[RiskCheckRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
