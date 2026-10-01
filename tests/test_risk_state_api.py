"""Contract tests for the read-only risk-state panel endpoint."""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

from bananatrade.risk import RiskConfig
from bananatrade.risk_state_api import (
    RiskStateRequestHandler,
    build_risk_state_response,
    make_risk_state_handler,
)


def test_normal_state_returns_panel_metrics_and_no_rejections() -> None:
    result = build_risk_state_response(
        {
            "kill_switch": False,
            "daily_pnl": 125.0,
            "equity": 10_000.0,
            "exposure": 2_500.0,
            "trades_today": 2,
            "consecutive_losses": 1,
            "last_rejection_reasons": [],
        }
    )

    assert result == {
        "kill_switch": False,
        "daily_pnl_pct": pytest.approx(1.25),
        "exposure": pytest.approx(2_500.0),
        "trades_today": 2,
        "cooldown_active": False,
        "last_rejection_reasons": [],
    }


def test_kill_switch_engaged_state_preserves_rejection_reasons() -> None:
    result = build_risk_state_response(
        kill_switch=True,
        daily_pnl_pct=-3.5,
        exposure=4_000.0,
        trades_today=4,
        cooldown_active=False,
        last_rejection_reasons=["kill switch active", "daily loss limit exceeded"],
    )

    assert result == {
        "kill_switch": True,
        "daily_pnl_pct": pytest.approx(-3.5),
        "exposure": pytest.approx(4_000.0),
        "trades_today": 4,
        "cooldown_active": False,
        "last_rejection_reasons": ["kill switch active", "daily loss limit exceeded"],
    }


def test_cooldown_state_is_derived_from_consecutive_losses() -> None:
    result = build_risk_state_response(
        {
            "daily_pnl_pct": -2.0,
            "exposure": 1_000.0,
            "trades_today": 3,
            "consecutive_losses": 3,
            "last_rejection_reasons": ["loss cooldown active"],
        },
        risk_config=RiskConfig(cooldown_losses=3),
    )

    assert result["cooldown_active"] is True
    assert result["last_rejection_reasons"] == ["loss cooldown active"]


def test_http_get_risk_state_returns_json() -> None:
    server = _start_server(
        make_risk_state_handler(
            {
                "kill_switch": False,
                "daily_pnl_pct": 0.5,
                "exposure": 750.0,
                "trades_today": 1,
                "cooldown_active": True,
                "last_rejection_reasons": ["loss cooldown active"],
            }
        )
    )
    try:
        response, result = _get(server, "/api/risk/state")
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert result == {
        "kill_switch": False,
        "daily_pnl_pct": pytest.approx(0.5),
        "exposure": pytest.approx(750.0),
        "trades_today": 1,
        "cooldown_active": True,
        "last_rejection_reasons": ["loss cooldown active"],
    }


def test_handler_only_serves_risk_state_path() -> None:
    server = _start_server(make_risk_state_handler({}))
    try:
        response, _ = _get(server, "/api/other")
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 404


def _start_server(handler: type[RiskStateRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _get(server: ThreadingHTTPServer, path: str) -> tuple[Any, dict[str, Any]]:
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        result = json.loads(response.read()) if response.status == 200 else {}
        return response, result
    finally:
        connection.close()
