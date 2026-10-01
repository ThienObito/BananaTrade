"""Contract tests for the read-only quota panel endpoint."""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from bananatrade.gateway.quota import QuotaLedger
from bananatrade.quota_api import (
    QuotaRequestHandler,
    build_quota_response,
    make_quota_handler,
)

TIERS: dict[str, dict[str, object]] = {
    "tier1_fast": {
        "quota": {"max_calls_per_5h": 100, "max_calls_per_7d": 500},
    },
    "tier2_analyst": {
        "quota": {"max_calls_per_5h": 50, "max_calls_per_7d": 250},
    },
    "tier4_cio": {
        "quota": {"max_calls_per_5h": 10, "max_calls_per_7d": 30},
    },
}
EXPECTED_LIMITS: dict[str, tuple[int, int]] = {
    "tier1_fast": (100, 500),
    "tier2_analyst": (50, 250),
    "tier4_cio": (10, 30),
}


def test_normal_ledger_state_returns_usage_limits_and_cio_highlight(tmp_path: Path) -> None:
    ledger = QuotaLedger(tmp_path / "quota.db")
    ledger.record("tier1_fast", 120)
    ledger.record("tier1_fast", 80)
    ledger.record("tier2_analyst", 40)
    ledger.record("tier2_analyst", 0, status="failed")
    ledger.record("tier4_cio", 300)

    result = build_quota_response(ledger, TIERS)

    assert result == {
        "tiers": {
            "tier1_fast": {
                "windows": {
                    "5h": {"used": 2, "limit": 100},
                    "7d": {"used": 2, "limit": 500},
                },
                "flagged": False,
                "highlighted": False,
            },
            "tier2_analyst": {
                "windows": {
                    "5h": {"used": 1, "limit": 50},
                    "7d": {"used": 1, "limit": 250},
                },
                "flagged": False,
                "highlighted": False,
            },
            "tier4_cio": {
                "windows": {
                    "5h": {"used": 1, "limit": 10},
                    "7d": {"used": 1, "limit": 30},
                },
                "flagged": True,
                "highlighted": True,
            },
        }
    }


def test_http_endpoint_marks_tier_near_its_limit(tmp_path: Path) -> None:
    ledger = QuotaLedger(tmp_path / "quota.db")
    for _ in range(9):
        ledger.record("tier4_cio", 1)

    server = _start_server(make_quota_handler(ledger, TIERS))
    try:
        response, result = _get(server, "/api/quota")
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert result["tiers"]["tier4_cio"]["windows"] == {
        "5h": {"used": 9, "limit": 10},
        "7d": {"used": 9, "limit": 30},
    }
    assert result["tiers"]["tier4_cio"]["flagged"] is True
    assert result["tiers"]["tier4_cio"]["highlighted"] is True


def test_empty_ledger_returns_zero_usage_for_every_tier(tmp_path: Path) -> None:
    ledger = QuotaLedger(tmp_path / "quota.db")

    result = build_quota_response(ledger, TIERS)

    for tier, payload in result["tiers"].items():
        expected_5h, expected_7d = EXPECTED_LIMITS[tier]
        assert payload["windows"]["5h"]["used"] == 0
        assert payload["windows"]["7d"]["used"] == 0
        assert payload["windows"]["5h"]["limit"] == expected_5h
        assert payload["windows"]["7d"]["limit"] == expected_7d


def test_handler_only_serves_quota_path(tmp_path: Path) -> None:
    ledger = QuotaLedger(tmp_path / "quota.db")
    server = _start_server(make_quota_handler(ledger, TIERS))
    try:
        response, _ = _get(server, "/api/other")
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 404


def _start_server(handler: type[QuotaRequestHandler]) -> ThreadingHTTPServer:
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
