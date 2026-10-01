from __future__ import annotations

from types import SimpleNamespace

import pytest

from bananatrade.brain import Decision
from bananatrade.brokers.mt5_client import MT5SymbolSpec
from bananatrade.brokers.mt5_executor import LiveAccountRefused, MT5Executor, MT5OrderRefused
from bananatrade.config import Config


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    def __init__(self, mode=0, positions=None, pnl=0.0):
        self.mode = mode
        self.positions = positions or []
        self.pnl = pnl
        self.order_send_calls = 0
        self.order_check_calls = 0
        self.requests = []

    def account_info(self):
        return SimpleNamespace(trade_mode=self.mode, equity=10000.0, profit=self.pnl)

    def positions_get(self, **kwargs):
        return self.positions

    def order_check(self, request):
        self.order_check_calls += 1
        return SimpleNamespace(retcode=10009, comment="done")

    def order_send(self, request):
        self.order_send_calls += 1
        self.requests.append(request)
        return SimpleNamespace(retcode=10009, order=42, deal=43, comment="done")


SPEC = MT5SymbolSpec("XAUUSDm", 2, 0.01, 0.01, 0.01, 10.0, 10, 3, 0.1)
DECISION = Decision("BUY", 0.8, 100.0, 99.0, 102.0, 0.37, ["test"])


def executor(module=None, enabled=False, **kwargs):
    return MT5Executor(Config(mt5_execution_enabled=enabled, mt5_volume_max=0.2, **kwargs), module or FakeMT5())


def test_demo_account_allows_guard():
    assert executor().status()["account_mode"] == "DEMO"


def test_live_account_refused_and_disabled():
    value = executor(FakeMT5(mode=1))
    with pytest.raises(LiveAccountRefused):
        value.execute("XAUUSDm", DECISION, SPEC)
    assert value.disabled


def test_enabled_config_cannot_bypass_live_account_guard():
    value = executor(FakeMT5(mode=1), enabled=True)
    with pytest.raises(LiveAccountRefused, match="non-demo"):
        value.execute("XAUUSDm", DECISION, SPEC)
    assert value.mt5.order_send_calls == 0


def test_disabled_after_refusal_stays_refused():
    value = executor(FakeMT5(mode=1))
    with pytest.raises(LiveAccountRefused):
        value.execute("XAUUSDm", DECISION, SPEC)
    with pytest.raises(LiveAccountRefused):
        value.execute("XAUUSDm", DECISION, SPEC)


def test_dry_run_never_calls_order_send():
    module = FakeMT5()
    result = executor(module).execute("XAUUSDm", DECISION, SPEC)
    assert result.dry_run
    assert module.order_send_calls == 0
    assert module.order_check_calls == 0


def test_enabled_runs_order_check_then_send():
    module = FakeMT5()
    result = executor(module, True).execute("XAUUSDm", DECISION, SPEC)
    assert result.sent
    assert module.order_check_calls == 1
    assert module.order_send_calls == 1


def test_none_decision_never_sends():
    module = FakeMT5()
    result = executor(module, True).execute("XAUUSDm", Decision("NONE", 0.1, None, None, None, 0, ["blocked"]), SPEC)
    assert result.dry_run
    assert module.order_send_calls == 0


def test_missing_sl_refused():
    with pytest.raises(MT5OrderRefused, match="required"):
        executor().execute("XAUUSDm", Decision("BUY", 0.8, 100, None, 102, 0.1), SPEC)


def test_missing_tp_refused():
    with pytest.raises(MT5OrderRefused, match="required"):
        executor().execute("XAUUSDm", Decision("BUY", 0.8, 100, 99, None, 0.1), SPEC)


def test_stops_level_refused():
    with pytest.raises(MT5OrderRefused, match="stops_level"):
        executor().execute("XAUUSDm", Decision("BUY", 0.8, 100, 99.99, 100.01, 0.1), SPEC)


def test_daily_loss_kill_switch():
    with pytest.raises(MT5OrderRefused, match="daily loss"):
        executor().execute("XAUUSDm", DECISION, SPEC, today_pnl=-300.0)


def test_one_position_per_symbol():
    module = FakeMT5(positions=[SimpleNamespace(symbol="XAUUSDm", magic=59040, ticket=1, volume=0.1)])
    with pytest.raises(MT5OrderRefused, match="one position"):
        executor(module).execute("XAUUSDm", DECISION, SPEC)


def test_volume_capped_and_rounded():
    module = FakeMT5()
    executor(module, True).execute("XAUUSDm", replace_decision(0.99), SPEC)
    assert module.requests[0]["volume"] == pytest.approx(0.2)


def replace_decision(volume):
    return Decision("BUY", 0.8, 100, 99, 102, volume, ["test"])


def test_magic_and_comment_are_fixed():
    module = FakeMT5()
    executor(module, True).execute("XAUUSDm", DECISION, SPEC)
    assert module.requests[0]["magic"] == 59040
    assert module.requests[0]["comment"] == "BananaTrade-DEMO"


def test_close_all_positions_dry_run_never_sends():
    module = FakeMT5(positions=[SimpleNamespace(symbol="XAUUSDm", magic=59040, ticket=1, volume=0.1)])
    results = executor(module).close_all_positions(59040)
    assert results[0].dry_run
    assert module.order_send_calls == 0


def test_close_all_positions_filters_magic():
    module = FakeMT5(positions=[SimpleNamespace(symbol="XAUUSDm", magic=1, ticket=1, volume=0.1)])
    assert executor(module).close_all_positions(59040) == []


def test_order_check_rejection_blocks_send():
    class Reject(FakeMT5):
        def order_check(self, request):
            return SimpleNamespace(retcode=10013, comment="invalid")
    module = Reject()
    with pytest.raises(MT5OrderRefused, match="order_check"):
        executor(module, True).execute("XAUUSDm", DECISION, SPEC)
    assert module.order_send_calls == 0


def test_order_send_requote_is_reported():
    class Requote(FakeMT5):
        def order_send(self, request):
            self.order_send_calls += 1
            return SimpleNamespace(retcode=10004, comment="requote")
    with pytest.raises(MT5OrderRefused, match="order_send"):
        executor(Requote(), True).execute("XAUUSDm", DECISION, SPEC)
