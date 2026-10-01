import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from typing import Any

import pytest

from bananatrade import web_server
from bananatrade.engine.strategy import MACrossStrategy
from bananatrade.paper_broker import PaperBroker
from bananatrade.risk_manager import RiskManager


def test_risk_manager_allows_valid_position() -> None:
    result = RiskManager().check_can_open(10_000.0, 0.0, 0, 500.0)
    assert result.allowed is True
    assert result.reason == "risk checks passed"


def test_risk_manager_blocks_max_open_positions() -> None:
    result = RiskManager(max_open_positions=3).check_can_open(10_000.0, 0.0, 3, 100.0)
    assert result.allowed is False
    assert "open positions" in result.reason


def test_risk_manager_blocks_daily_loss() -> None:
    result = RiskManager().check_can_open(10_000.0, -200.0, 0, 100.0)
    assert result.allowed is False
    assert "daily loss" in result.reason


def test_risk_manager_allows_loss_below_limit() -> None:
    result = RiskManager().check_can_open(10_000.0, -199.0, 0, 100.0)
    assert result.allowed is True


def test_risk_manager_blocks_position_size() -> None:
    result = RiskManager().check_can_open(10_000.0, 0.0, 0, 1_001.0)
    assert result.allowed is False
    assert "position size" in result.reason


def test_risk_manager_allows_position_at_limit() -> None:
    result = RiskManager().check_can_open(10_000.0, 0.0, 0, 1_000.0)
    assert result.allowed is True


def test_risk_manager_blocks_non_positive_equity() -> None:
    result = RiskManager().check_can_open(0.0, 0.0, 0, 1.0)
    assert result.allowed is False
    assert "equity" in result.reason


def test_risk_manager_blocks_non_finite_daily_pnl() -> None:
    result = RiskManager().check_can_open(10_000.0, float("inf"), 0, 1.0)
    assert result.allowed is False
    assert "finite" in result.reason


def test_risk_manager_blocks_negative_open_count() -> None:
    result = RiskManager().check_can_open(10_000.0, 0.0, -1, 1.0)
    assert result.allowed is False
    assert "open_count" in result.reason


def test_risk_manager_blocks_negative_size() -> None:
    result = RiskManager().check_can_open(10_000.0, 0.0, 0, -1.0)
    assert result.allowed is False
    assert "proposed_size" in result.reason


def test_drawdown_below_threshold_does_not_halt() -> None:
    assert RiskManager().check_drawdown(9_000.0, 10_000.0) is False


def test_drawdown_at_threshold_does_not_halt() -> None:
    assert RiskManager().check_drawdown(9_000.0, 10_000.0) is False


def test_drawdown_above_threshold_halts() -> None:
    assert RiskManager().check_drawdown(8_999.0, 10_000.0) is True


def test_drawdown_invalid_equity_halts() -> None:
    assert RiskManager().check_drawdown(0.0, 10_000.0) is True


def test_risk_manager_constructor_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        RiskManager(max_open_positions=-1)
    with pytest.raises(ValueError):
        RiskManager(max_daily_loss_pct=1.1)
    with pytest.raises(ValueError):
        RiskManager(max_position_size_pct=-0.1)


def _volatile_candles() -> list[dict[str, object]]:
    candles = [{"close": 100.0, "high": 100.5, "low": 99.5, "volume": 1.0} for _ in range(50)]
    candles.append({"close": 100.0, "high": 200.0, "low": 0.0, "volume": 1.0})
    return candles


def test_strategy_volatility_filter_blocks_signal() -> None:
    result = MACrossStrategy().generate_signal(_volatile_candles())
    assert result.bias == "NEUTRAL"
    assert "volatility" in result.reason


def test_strategy_volume_filter_placeholder_passes() -> None:
    candles = [{"close": 100.0, "high": 100.1, "low": 99.9, "volume": 1.0} for _ in range(51)]
    result = MACrossStrategy().generate_signal(candles)
    assert "volume filter" not in result.reason


@contextmanager
def running_server() -> Iterator[tuple[str, int]]:
    server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_risk_endpoint_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))
    with running_server() as (host, port):
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/risk")
        response = connection.getresponse()
        payload: Any = json.loads(response.read().decode("utf-8"))
        connection.close()
    assert response.status == 200
    assert set(payload) == {
        "open_positions", "daily_pnl", "daily_pnl_pct", "peak_equity",
        "current_equity", "drawdown_pct", "trading_halted",
    }


def test_risk_endpoint_starts_flat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_server, "BROKER", PaperBroker(1_000.0))
    payload = web_server.risk_state()
    assert payload["open_positions"] == 0
    assert payload["daily_pnl"] == 0.0
    assert payload["trading_halted"] is False


def test_risk_endpoint_reports_open_position(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "BUY", 1.0, 100.0)
    monkeypatch.setattr(web_server, "BROKER", broker)
    payload = web_server.risk_state()
    assert payload["open_positions"] == 1
    assert payload["current_equity"] == 1_000.0
