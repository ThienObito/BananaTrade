"""MT5 run path: real account state, lot sizing from tick value, fail-closed kill switch."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bananatrade.brain import Brain
from bananatrade.brokers.mt5_client import MT5Client, MT5ConnectionError, MT5SymbolSpec
from bananatrade.brokers.mt5_executor import MT5Executor, MT5OrderRefused
from bananatrade.config import Config
from bananatrade.engine.ensemble_signal import EnsembleSignal, SignalScore
from bananatrade.engine.execution_model import ExecutionModel


class FakeTerminal:
    """Demo terminal for EURUSD (5 digits, 100k contract, $1 per 0.00001 tick per lot)."""

    ACCOUNT_TRADE_MODE_DEMO = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    def __init__(self, equity: float = 10_000.0, deals=(), positions=(), mode: int = 0) -> None:
        self.equity = equity
        self.deals = list(deals)
        self.positions = list(positions)
        self.mode = mode
        self.sent = 0
        self.shut = False

    def initialize(self):
        return True

    def shutdown(self):
        self.shut = True

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return SimpleNamespace(trade_mode=self.mode, equity=self.equity, balance=self.equity, profit=0.0)

    def symbols_get(self):
        return [SimpleNamespace(name="EURUSD")]

    def symbol_select(self, name, flag):
        return True

    def symbol_info(self, name):
        return SimpleNamespace(digits=5, point=0.00001, volume_min=0.01, volume_step=0.01, volume_max=100.0,
                               trade_stops_level=0, filling_mode=1, trade_tick_value=1.0,
                               trade_tick_size=0.00001, trade_contract_size=100_000.0)

    def symbol_info_tick(self, name):
        return SimpleNamespace(bid=1.10000, ask=1.10010, last=0.0, time=1_700_000_000)

    def order_calc_margin(self, order_type, symbol, volume, price):
        return 110.0 * volume  # 1:1000 leverage on 110k notional

    def history_deals_get(self, start, end):
        return self.deals

    def positions_get(self, **kwargs):
        return self.positions

    def copy_rates_from_pos(self, name, timeframe, start, count):
        return [
            {"time": 1_700_000_000 + 900 * i, "open": 1.1 + i * 1e-5, "high": 1.1003 + i * 1e-5,
             "low": 1.0997 + i * 1e-5, "close": 1.1001 + i * 1e-5, "tick_volume": 100, "spread": 10, "real_volume": 0}
            for i in range(count)
        ]

    def order_check(self, request):
        raise AssertionError("dry-run must not call order_check")

    def order_send(self, request):
        self.sent += 1
        raise AssertionError("dry-run must not call order_send")


def test_symbol_spec_reports_tick_value_and_margin() -> None:
    spec = MT5Client(FakeTerminal()).symbol_spec("EURUSD")
    assert spec.tick_value == 1.0 and spec.tick_size == 0.00001
    assert spec.contract_size == 100_000.0
    assert spec.margin_per_lot == 110.0


def test_account_state_uses_real_equity_and_today_pnl() -> None:
    deals = [SimpleNamespace(profit=-150.0, commission=-7.0, swap=0.0, fee=0.0)]
    positions = [SimpleNamespace(symbol="EURUSD", profit=-20.0), SimpleNamespace(symbol="XAUUSD", profit=5.0)]
    state = MT5Client(FakeTerminal(9_000.0, deals, positions)).account_state("EURUSD")
    assert state["equity"] == 9_000.0
    assert state["daily_pnl"] == pytest.approx(-172.0)
    assert state["open_count"] == 1


def test_account_state_without_equity_raises() -> None:
    with pytest.raises(MT5ConnectionError):
        MT5Client(FakeTerminal(0.0)).account_state("EURUSD")


class LongEnsemble(EnsembleSignal):
    def score(self, candles):
        return SignalScore("LONG", 0.95, {"ma_cross_score": 1.0})


def _candles(n: int = 100) -> list[dict[str, object]]:
    return [{"timestamp": i, "open": 1.1, "high": 1.1010, "low": 1.0990, "close": 1.1 + i * 1e-6} for i in range(n)]


def _spec(**overrides) -> dict[str, object]:
    spec = vars(MT5Client(FakeTerminal()).symbol_spec("EURUSD"))
    spec.update(overrides)
    return spec


def test_brain_sizes_lots_from_risk_budget(tmp_path: Path) -> None:
    brain = Brain(ensemble=LongEnsemble(), execution_model=ExecutionModel(10_000.0, 0.01), decision_log_path=tmp_path / "d.csv")
    account = {"equity": 10_000.0, "daily_pnl": 0.0, "open_count": 0, "bid": 1.1, "ask": 1.1001}
    decision = brain.decide(_candles(), _spec(), account)
    assert decision.side == "BUY", decision.reasons
    loss_at_sl = abs(decision.entry - decision.sl) / 0.00001 * 1.0 * decision.volume  # type: ignore[operator]
    assert loss_at_sl <= 100.0 + 1e-6  # never more than 1% of equity
    assert loss_at_sl > 50.0  # and not absurdly small
    assert abs(decision.volume / 0.01 - round(decision.volume / 0.01)) < 1e-9


def test_brain_refuses_when_min_lot_exceeds_risk(tmp_path: Path) -> None:
    brain = Brain(ensemble=LongEnsemble(), execution_model=ExecutionModel(10.0, 0.01), decision_log_path=tmp_path / "d.csv")
    account = {"equity": 10.0, "daily_pnl": 0.0, "open_count": 0, "bid": 1.1, "ask": 1.1001}
    decision = brain.decide(_candles(), _spec(), account)
    assert decision.side == "NONE"
    assert decision.reasons == ["risk budget below symbol minimum lot"]


def test_executor_kill_switch_fails_closed_without_equity() -> None:
    spec = MT5SymbolSpec("EURUSD", 5, 0.00001, 0.01, 0.01, 100.0, 0, 1, 0.0001)
    from bananatrade.brain import Decision

    with pytest.raises(MT5OrderRefused, match="equity unavailable"):
        MT5Executor(Config(), FakeTerminal(0.0)).execute("EURUSD", Decision("BUY", 0.9, 1.1, 1.099, 1.102, 0.1, []), spec)


def test_cli_mt5_run_end_to_end_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bananatrade import cli

    terminal = FakeTerminal()
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "MT5Client", lambda cache_dir=None: MT5Client(terminal, cache_dir or tmp_path))
    real_executor = cli.MT5Executor
    monkeypatch.setattr(cli, "MT5Executor", lambda config, module: real_executor(config, terminal))
    result = cli._run_mt5_once(Config(), "EURUSD")
    assert result["symbol"] == "EURUSD"
    assert result["account"]["equity"] == 10_000.0
    assert result["execution"]["dry_run"] is True
    assert terminal.sent == 0
    assert terminal.shut


def test_main_passes_string_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from bananatrade import cli

    seen = {}
    monkeypatch.setattr(cli, "run", lambda symbol, config, broker: seen.update(symbol=symbol, broker=broker))
    monkeypatch.setattr(sys, "argv", ["bananatrade", "run", "EURUSD", "--broker", "mt5"])
    cli.main()
    assert seen == {"symbol": "EURUSD", "broker": "mt5"}
    monkeypatch.setattr(sys, "argv", ["bananatrade", "run", "--broker", "mt5"])
    cli.main()
    assert isinstance(seen["symbol"], str)


def test_rates_from_real_numpy_structured_array(tmp_path: Path) -> None:
    """MetaTrader5.copy_rates_* returns a numpy structured array (rows are numpy.void)."""
    import numpy as np

    dtype = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"),
             ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")]
    arr = np.array([(1_700_000_000, 1.1, 1.2, 1.0, 1.15, 10, 7, 0), (1_700_000_900, 1.15, 1.25, 1.1, 1.2, 12, 8, 0)], dtype=dtype)

    class NumpyTerminal(FakeTerminal):
        def copy_rates_from_pos(self, name, timeframe, start, count):
            return arr

    rows = MT5Client(NumpyTerminal(), tmp_path).get_rates("EURUSD", 15, 2)
    assert rows[0]["timestamp"] == 1_700_000_000 and isinstance(rows[0]["timestamp"], int)
    assert rows[1]["close"] == 1.2 and rows[1]["spread"] == 8.0


def test_account_state_ignores_deposits_and_handles_no_deals() -> None:
    deals = [SimpleNamespace(type=2, profit=5_000.0, commission=0.0, swap=0.0, fee=0.0),  # DEAL_TYPE_BALANCE
             SimpleNamespace(type=1, profit=-40.0, commission=-3.0, swap=0.0, fee=0.0)]
    assert MT5Client(FakeTerminal(deals=deals)).account_state("EURUSD")["daily_pnl"] == pytest.approx(-43.0)

    class NoDeals(FakeTerminal):
        def history_deals_get(self, start, end):
            return None

        def last_error(self):
            return (1, "Success")

    assert MT5Client(NoDeals()).account_state("EURUSD")["daily_pnl"] == 0.0

    class Broken(NoDeals):
        def last_error(self):
            return (-10004, "No IPC connection")

    with pytest.raises(MT5ConnectionError):
        MT5Client(Broken()).account_state("EURUSD")
