import csv
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from typing import Literal

import pytest

from bananatrade import web_server
from bananatrade.backtest.engine import BacktestEngine, BacktestResult
from bananatrade.backtest.report import generate_report, save_csv
from bananatrade.engine.strategy import SignalResult


class FixedStrategy:
    def __init__(self, bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG") -> None:
        self.bias = bias

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        return SignalResult(self.bias, 1.0, "test signal")


def candles(count: int = 100, close: float = 100.0) -> list[dict[str, object]]:
    return [{"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0} for _ in range(count)]


def test_engine_runs_on_100_bar_synthetic_data() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert len(result.equity_curve) == 101
    assert result.total_trades == 1


def test_engine_returns_backtest_result() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert isinstance(result, BacktestResult)
    assert isinstance(result.trades, list)


def test_engine_fills_at_next_open() -> None:
    data = candles(55)
    data[1]["open"] = 110.0
    data[1]["close"] = 110.0
    result = BacktestEngine().run(data, FixedStrategy())
    assert result.trades[0]["entry"] == 110.0


def test_engine_correct_long_pnl() -> None:
    data = candles(55)
    data[51].update({"open": 100.0, "high": 130.0, "low": 100.0, "close": 125.0})
    result = BacktestEngine().run(data, FixedStrategy())
    trade = result.trades[0]
    assert isinstance(trade["pnl"], (int, float))
    assert trade["pnl"] > 0
    assert trade["exit"] == 103.0


def test_engine_correct_short_pnl() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy("SHORT"))
    assert result.trades[0]["side"] == "SHORT"
    assert result.trades[0]["pnl"] == 0.0


def test_engine_stop_loss_exit() -> None:
    data = candles(55)
    data[52].update({"open": 100.0, "high": 100.0, "low": 95.0, "close": 96.0})
    result = BacktestEngine().run(data, FixedStrategy())
    assert result.trades[0]["reason"] == "stop_loss"


def test_engine_take_profit_exit() -> None:
    data = candles(55)
    data[52].update({"open": 100.0, "high": 104.0, "low": 100.0, "close": 103.0})
    result = BacktestEngine().run(data, FixedStrategy())
    assert result.trades[0]["reason"] == "take_profit"


def test_engine_end_of_data_closes_position() -> None:
    result = BacktestEngine().run(candles(51), FixedStrategy())
    assert result.trades[0]["reason"] == "end_of_data"


def test_total_return_percent_is_calculated() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert result.total_return_pct == pytest.approx(0.0)


def test_max_drawdown_calculation() -> None:
    result = BacktestResult([], [100.0, 120.0, 90.0, 100.0], -0.0, 0.0, 0.0, 0.0, 0)
    calculated = BacktestEngine._result(result.trades, result.equity_curve, 100.0)
    assert calculated.max_drawdown_pct == pytest.approx(25.0)


def test_sharpe_calculation_is_finite() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert result.sharpe_ratio == pytest.approx(0.0)


def test_win_rate_zero_for_flat_trade() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert result.win_rate == 0.0


def test_total_trades_matches_trade_list() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    assert result.total_trades == len(result.trades)


def test_empty_candles_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        BacktestEngine().run([], FixedStrategy())


def test_invalid_initial_equity_rejected() -> None:
    with pytest.raises(ValueError, match="initial_equity"):
        BacktestEngine().run(candles(), FixedStrategy(), 0.0)


def test_report_contains_all_metrics() -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    report = generate_report(result)
    assert set(report) == {"total_return_pct", "max_drawdown_pct", "sharpe_ratio", "win_rate", "total_trades", "summary"}
    assert "trades" in report["summary"]


def test_save_csv_writes_equity_and_trades(tmp_path: Path) -> None:
    result = BacktestEngine().run(candles(), FixedStrategy())
    equity_path, trades_path = save_csv(result, tmp_path)
    assert equity_path.exists()
    assert trades_path.exists()
    with equity_path.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == ["index", "equity"]
    with trades_path.open(newline="", encoding="utf-8") as handle:
        assert "pnl" in next(csv.DictReader(handle))


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


def test_backtest_endpoint_returns_200_with_schema() -> None:
    with running_server() as (host, port):
        connection = HTTPConnection(host, port, timeout=5)
        body = json.dumps({"candles": candles(), "initial_equity": 10_000.0})
        connection.request("POST", "/api/backtest", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
    assert response.status == 200
    assert {"trades", "equity_curve", "total_return_pct", "max_drawdown_pct", "sharpe_ratio", "win_rate", "total_trades", "summary"} <= set(payload)


def test_backtest_endpoint_rejects_missing_candles() -> None:
    with running_server() as (host, port):
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("POST", "/api/backtest", body="{}", headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
    assert response.status == 400
    assert "candles" in payload["error"]
