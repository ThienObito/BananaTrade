from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

from bananatrade import web_server
from bananatrade.brokers.mt5_executor import MT5Executor
from bananatrade.config import Config


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0

    def account_info(self):
        return SimpleNamespace(trade_mode=0, equity=10000.0, profit=12.5)

    def positions_get(self, **kwargs):
        return []


@contextmanager
def server() -> Iterator[tuple[str, int]]:
    current = web_server.MT5_EXECUTOR
    web_server.MT5_EXECUTOR = MT5Executor(Config(), FakeMT5())
    instance = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = instance.server_address
        assert isinstance(host, str) and isinstance(port, int)
        yield host, port
    finally:
        instance.shutdown()
        thread.join(timeout=5)
        instance.server_close()
        web_server.MT5_EXECUTOR = current


def test_mt5_status_endpoint_exact_keys():
    with server() as (host, port):
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/mt5_status")
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
    assert response.status == 200
    assert set(body) == {"connected", "account_mode", "execution_enabled", "last_decision", "open_positions", "today_pnl"}
    assert body["account_mode"] == "DEMO"


def test_mt5_status_defaults_execution_off():
    with server() as (host, port):
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/mt5_status")
        body = json.loads(connection.getresponse().read())
        connection.close()
    assert body["execution_enabled"] is False


def test_cli_parser_accepts_mt5_broker():
    from bananatrade.cli import build_parser

    args = build_parser().parse_args(["run", "--broker", "mt5"])
    assert args.broker == "mt5"


def test_cli_parser_keeps_paper_default():
    from bananatrade.cli import build_parser

    args = build_parser().parse_args(["run"])
    assert args.broker == "paper"


def test_mt5_endpoint_reports_zero_positions():
    with server() as (host, port):
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/mt5_status")
        body = json.loads(connection.getresponse().read())
        connection.close()
    assert body["open_positions"] == 0


def test_mt5_endpoint_reports_account_pnl():
    with server() as (host, port):
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/mt5_status")
        body = json.loads(connection.getresponse().read())
        connection.close()
    assert body["today_pnl"] == 12.5
