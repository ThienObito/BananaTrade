from pathlib import Path
from typing import Literal

import pytest

from bananatrade.agents.execution.auto_trader import AutoTrader
from bananatrade.engine.adaptive_trader import AdaptiveTrader
from bananatrade.engine.entry_optimizer import EntryOptimizer, LimitEntry
from bananatrade.engine.exit_manager import ExitManager, PartialExit
from bananatrade.engine.regime_detector import Regime
from bananatrade.engine.strategy import SignalResult
from bananatrade.engine.trade_journal import TradeJournal
from bananatrade.paper_broker import PaperBroker


def candles(price: float = 100.0, atr14: float = 2.0, count: int = 20) -> list[dict[str, object]]:
    return [{"open": price, "high": price + atr14, "low": price - atr14, "close": price, "atr14": atr14, "volume": 1.0} for _ in range(count)]


def signal(bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG") -> SignalResult:
    return SignalResult(bias, 0.9, "test")


def position(side: str = "LONG", quantity: float = 10.0) -> dict[str, object]:
    return {"symbol": "BTC/USDT", "side": side, "quantity": quantity, "entry": 100.0, "stop_loss": 96.0, "take_profit": 110.0, "atr14": 4.0}


class AllowMtf:
    def confirm(self, candles_1m: object, candles_5m: object | None = None) -> bool:
        return True


def trader(tmp_path: Path, bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG") -> AdaptiveTrader:
    class Fixed:
        def generate_signal(self, data: object) -> SignalResult:
            return signal(bias)

    return AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), strategy=Fixed(), mtf_signal=AllowMtf(), entry_optimizer=EntryOptimizer(), journal=TradeJournal(tmp_path / "j.csv"))


def test_limit_entry_type() -> None:
    result = EntryOptimizer().compute_limit_entry(signal(), candles(), Regime.RANGING)
    assert isinstance(result, LimitEntry)


def test_limit_buy_below_close() -> None:
    result = EntryOptimizer().compute_limit_entry(signal("LONG"), candles(), Regime.RANGING)
    assert result is not None
    assert result.price == pytest.approx(99.4)
    assert result.price < 100.0


def test_limit_sell_above_close() -> None:
    result = EntryOptimizer().compute_limit_entry(signal("SHORT"), candles(), Regime.RANGING)
    assert result is not None
    assert result.price == pytest.approx(100.6)
    assert result.price > 100.0


def test_limit_expiry_two_bars() -> None:
    result = EntryOptimizer().compute_limit_entry(signal(), candles(), Regime.RANGING)
    assert result is not None
    assert result.expiry_bars == 2


def test_limit_none_volatile() -> None:
    assert EntryOptimizer().compute_limit_entry(signal(), candles(), Regime.VOLATILE) is None


def test_limit_none_neutral() -> None:
    assert EntryOptimizer().compute_limit_entry(signal("NEUTRAL"), candles(), Regime.RANGING) is None


def test_limit_uses_atr() -> None:
    result = EntryOptimizer().compute_limit_entry(signal(), candles(atr14=4.0), Regime.RANGING)
    assert result is not None
    assert result.price == pytest.approx(98.8)


def test_limit_uses_latest_close() -> None:
    data = candles()
    data[-1]["close"] = 110.0
    result = EntryOptimizer().compute_limit_entry(signal(), data, Regime.RANGING)
    assert result is not None
    assert result.price == pytest.approx(109.4)


def test_limit_empty_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        EntryOptimizer().compute_limit_entry(signal(), [], Regime.RANGING)


def test_limit_bad_regime_rejected() -> None:
    with pytest.raises(TypeError, match="Regime"):
        EntryOptimizer().compute_limit_entry(signal(), candles(), object())


def test_limit_short_uses_positive_offset() -> None:
    result = EntryOptimizer().compute_limit_entry(signal("SHORT"), candles(atr14=4), Regime.TRENDING)
    assert result is not None
    assert result.price == pytest.approx(101.2)


def test_limit_fallback_atr() -> None:
    data: list[dict[str, object]] = [{"close": 100.0, "high": 101.0, "low": 99.0} for _ in range(20)]
    result = EntryOptimizer().compute_limit_entry(signal(), data, Regime.RANGING)
    assert result is not None
    assert result.price < 100.0


def test_partial_exit_type() -> None:
    result = ExitManager().partial_take_profit(position(), 107.0)
    assert isinstance(result, PartialExit)


def test_partial_tp_at_50_percent() -> None:
    pos = position(quantity=10.0)
    result = ExitManager().partial_take_profit(pos, 107.0)
    assert result is not None
    assert result.quantity == 5.0
    assert pos["quantity"] == 5.0


def test_partial_tp_price_recorded() -> None:
    result = ExitManager().partial_take_profit(position(), 107.0)
    assert result is not None
    assert result.price == 107.0


def test_partial_tp_reason() -> None:
    result = ExitManager().partial_take_profit(position(), 107.0)
    assert result is not None
    assert result.reason == "partial_take_profit"


def test_partial_tp_long_side() -> None:
    result = ExitManager().partial_take_profit(position(), 107.0)
    assert result is not None
    assert result.side == "SELL"


def test_partial_tp_short_side() -> None:
    result = ExitManager().partial_take_profit(position("SHORT"), 93.0)
    assert result is not None
    assert result.side == "BUY"


def test_partial_tp_moves_sl_breakeven() -> None:
    pos = position()
    ExitManager().partial_take_profit(pos, 107.0)
    assert pos["stop_loss"] == 100.0


def test_partial_tp_marks_hit() -> None:
    pos = position()
    ExitManager().partial_take_profit(pos, 107.0)
    assert pos["partial_tp_hit"] is True


def test_partial_tp_not_before_tp1() -> None:
    pos = position()
    assert ExitManager().partial_take_profit(pos, 105.0) is None
    assert pos["quantity"] == 10.0


def test_partial_tp_not_repeated() -> None:
    pos = position()
    manager = ExitManager()
    manager.partial_take_profit(pos, 107.0)
    assert manager.partial_take_profit(pos, 108.0) is None
    assert pos["quantity"] == 5.0


def test_partial_trails_long_remainder() -> None:
    pos = position()
    manager = ExitManager()
    manager.partial_take_profit(pos, 107.0)
    manager.partial_take_profit(pos, 112.0)
    assert pos["stop_loss"] == 108.0


def test_partial_trails_short_remainder() -> None:
    pos = position("SHORT")
    manager = ExitManager()
    manager.partial_take_profit(pos, 93.0)
    manager.partial_take_profit(pos, 88.0)
    assert pos["stop_loss"] == 92.0


def test_partial_trail_does_not_worsen_long() -> None:
    pos = position()
    manager = ExitManager()
    manager.partial_take_profit(pos, 107.0)
    manager.partial_take_profit(pos, 103.0)
    assert pos["stop_loss"] == 100.0


def test_partial_invalid_price() -> None:
    with pytest.raises(ValueError, match="positive"):
        ExitManager().partial_take_profit(position(), 0.0)


def test_partial_missing_atr() -> None:
    pos = position()
    del pos["atr14"]
    assert ExitManager().partial_take_profit(pos, 107.0) is None


def test_partial_zero_position() -> None:
    assert ExitManager().partial_take_profit(position(quantity=0.0), 107.0) is None


def test_adaptive_pending_limit_order(tmp_path: Path) -> None:
    current = trader(tmp_path)
    decision = current.run_once(current.broker.state(), candles(atr14=1.0))
    assert decision["action"] == "NONE"
    assert decision["reason"] == "limit entry pending"
    assert len(current.pending_limit_orders) == 1


def test_adaptive_limit_price_is_below_close(tmp_path: Path) -> None:
    current = trader(tmp_path)
    current.run_once(current.broker.state(), candles(atr14=1.0))
    price = current.pending_limit_orders[0]["price"]
    assert isinstance(price, (int, float))
    assert price < 100.0


def test_adaptive_expiry_after_two_bars(tmp_path: Path) -> None:
    current = trader(tmp_path)
    data = candles(atr14=1.0)
    current.run_once(current.broker.state(), data)
    current.run_once(current.broker.state(), data)
    assert len(current.pending_limit_orders) == 1
    current.run_once(current.broker.state(), data)
    assert len(current.pending_limit_orders) == 0


def test_adaptive_status_pending_count(tmp_path: Path) -> None:
    current = trader(tmp_path)
    current.run_once(current.broker.state(), candles(atr14=1.0))
    assert current.status()["pending_limit_orders"] == 1


def test_adaptive_status_partial_count(tmp_path: Path) -> None:
    current = trader(tmp_path)
    current.partial_exits_today = 2
    assert current.status()["partial_exits_today"] == 2


def test_adaptive_limit_short_above_close(tmp_path: Path) -> None:
    current = trader(tmp_path, "SHORT")
    current.run_once(current.broker.state(), candles(atr14=1.0))
    price = current.pending_limit_orders[0]["price"]
    assert isinstance(price, (int, float))
    assert price > 100.0


def test_adaptive_volatile_no_pending(tmp_path: Path) -> None:
    current = trader(tmp_path)
    data = candles(atr14=1.0)
    current.regime_detector._last = None
    current.entry_optimizer = EntryOptimizer()
    decision = current.run_once(current.broker.state(), data)
    assert decision["action"] == "NONE"


def test_partial_symbol_preserved() -> None:
    result = ExitManager().partial_take_profit(position(), 107.0)
    assert result is not None
    assert result.symbol == "BTC/USDT"
