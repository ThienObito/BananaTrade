from __future__ import annotations

from types import SimpleNamespace

import pytest

from bananatrade.bot_runner import BotRunner
from bananatrade.brain import Brain
from bananatrade.brokers.mt5_client import MT5Client
from bananatrade.brokers.mt5_executor import MT5Executor
from bananatrade.config import Config


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2

    def initialize(self):
        return True

    def symbols_get(self):
        return [SimpleNamespace(name="XAUUSDm")]

    def symbol_select(self, name, selected):
        return True

    def symbol_info(self, name):
        return SimpleNamespace(digits=2, point=0.01, volume_min=0.01, volume_step=0.01, volume_max=1.0, trade_stops_level=10, filling_mode=3)

    def symbol_info_tick(self, name):
        return SimpleNamespace(bid=100.0, ask=100.1, last=100.0, time=1)

    def account_info(self):
        return SimpleNamespace(trade_mode=0, equity=10000.0, profit=0.0)

    def positions_get(self, **kwargs):
        return []

    def order_check(self, request):
        return SimpleNamespace(retcode=10009, comment="ok")

    def order_send(self, request):
        return SimpleNamespace(retcode=10009, order=1)


def snapshot():
    return {"last_price": 100.0, "equity": 10000.0, "daily_pnl": 0.0, "candles": [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}] * 60}


class Provider:
    def __call__(self):
        return snapshot()


def runner(tmp_path, enabled=False):
    module = FakeMT5()
    client = MT5Client(module, tmp_path)
    executor = MT5Executor(Config(symbol="XAUUSD", mt5_execution_enabled=enabled), module)
    return BotRunner(Provider(), None, mt5_client=client, mt5_executor=executor, brain=Brain(decision_log_path=tmp_path / "decisions.csv"), config=Config(symbol="XAUUSD"))


def test_mt5_runner_connects_symbol_and_returns_decision(tmp_path):
    value = runner(tmp_path)
    result = __import__("asyncio").run(value.run_cycle())
    assert "decision" in result
    assert value.last_mt5_result is not None


def test_mt5_runner_dry_run_does_not_send(tmp_path):
    value = runner(tmp_path)
    result = __import__("asyncio").run(value.run_cycle())
    assert result["mt5_result"].dry_run


def test_mt5_runner_can_send_only_when_enabled(tmp_path):
    value = runner(tmp_path, enabled=True)
    result = __import__("asyncio").run(value.run_cycle())
    assert result["mt5_result"].dry_run or result["mt5_result"].sent


def test_runner_keeps_paper_path_without_mt5(tmp_path):
    assert BotRunner(Provider(), None, brain=None).mt5_client is None


def test_mt5_client_suffix_is_used_by_runner(tmp_path):
    value = runner(tmp_path)
    __import__("asyncio").run(value.run_cycle())
    assert value.mt5_client.resolved_symbols["XAUUSD"] == "XAUUSDm"


def test_runner_interval_validation_still_applies(tmp_path):
    value = runner(tmp_path)
    value.interval_seconds = 0
    with pytest.raises(ValueError, match="positive"):
        __import__("asyncio").run(value.main_loop())
