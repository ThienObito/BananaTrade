from typing import Literal

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.engine.strategy import SignalResult


class ScriptedStrategy:
    def __init__(self, signals: list[SignalResult]) -> None:
        self.signals = signals
        self.calls = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        signal = self.signals[min(self.calls, len(self.signals) - 1)]
        self.calls += 1
        return signal


def bars(count: int = 12, price: float = 100.0) -> list[dict[str, object]]:
    return [{"open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 10.0, "atr14": 1.0} for _ in range(count)]


def signal(bias: Literal["LONG", "SHORT", "NEUTRAL"], mode: Literal["market", "limit"] = "market", price: float | None = None) -> SignalResult:
    return SignalResult(bias, 1.0, "fixture", mode, price)


def test_default_fee_rate_is_taker_fee() -> None:
    assert BacktestEngine().fee_rate == pytest.approx(0.001)


def test_default_market_slippage_is_two_basis_points() -> None:
    assert BacktestEngine().slippage_pct == pytest.approx(0.0002)


def test_invalid_ohlc_is_rejected() -> None:
    data = bars()
    data[0].update({"low": 105.0, "high": 101.0})
    with pytest.raises(ValueError, match="inconsistent"):
        BacktestEngine().run(data, ScriptedStrategy([signal("LONG")]))


def test_infinite_atr_is_ignored() -> None:
    data = bars()
    data[0]["atr14"] = float("inf")
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG")]))
    assert result.total_trades == 1


def test_limit_expiry_boundary_does_not_fill_on_expiry_bar() -> None:
    data = bars(8)
    data[2]["low"] = 89.0
    result = BacktestEngine(fee_rate=0.0, limit_expiry_bars=1).run(data, ScriptedStrategy([signal("LONG", "limit", 90.0)]))
    assert result.total_trades == 0


def test_fee_reported_separately_from_gross_pnl() -> None:
    data = bars()
    data[3].update({"high": 104.0, "close": 103.0})
    result = BacktestEngine().run(data, ScriptedStrategy([signal("LONG")]))
    assert result.fees_paid > 0
    assert result.trades[0]["gross_pnl"] != result.trades[0]["net_pnl"]
    assert result.net_total_return_pct < result.total_return_pct


def test_market_entry_uses_next_bar_open_without_lookahead() -> None:
    data = bars()
    data[1]["open"] = 110.0
    data[1]["close"] = 110.0
    result = BacktestEngine(slippage_pct=0.0, fee_rate=0.0).run(data, ScriptedStrategy([signal("LONG")]))
    assert result.trades[0]["entry"] == 110.0


def test_market_slippage_changes_entry_fill() -> None:
    data = bars()
    data[1]["open"] = 110.0
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.001).run(data, ScriptedStrategy([signal("LONG")]))
    assert result.trades[0]["entry_fill"] == pytest.approx(110.11)


def test_limit_buy_fills_when_low_touches_limit() -> None:
    data = bars()
    data[1].update({"low": 98.0, "high": 101.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG", "limit", 99.0)]))
    assert result.limit_orders == 1
    assert result.limit_fills == 1
    assert result.trades[0]["entry"] == 99.0


def test_limit_sell_fills_when_high_touches_limit() -> None:
    data = bars()
    data[1].update({"low": 99.0, "high": 102.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("SHORT", "limit", 101.0)]))
    assert result.limit_fills == 1
    assert result.trades[0]["entry"] == 101.0


def test_limit_gap_through_fills_at_better_open() -> None:
    data = bars()
    data[1].update({"open": 98.0, "low": 97.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG", "limit", 99.0)]))
    assert result.trades[0]["entry"] == 98.0


def test_limit_expiry_cancels_unfilled_order() -> None:
    data = bars(8)
    result = BacktestEngine(fee_rate=0.0, limit_expiry_bars=1).run(data, ScriptedStrategy([signal("LONG", "limit", 90.0)]))
    assert result.limit_orders >= 1
    assert result.limit_fills == 0
    assert result.total_trades == 0


def test_limit_expiry_does_not_fill_after_expiry() -> None:
    data = bars(8)
    data[4]["low"] = 89.0
    result = BacktestEngine(fee_rate=0.0, limit_expiry_bars=1).run(data, ScriptedStrategy([signal("LONG", "limit", 90.0)]))
    assert result.total_trades == 0


def test_same_bar_stop_wins_over_take_profit() -> None:
    data = bars()
    data[2].update({"high": 105.0, "low": 95.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG")]))
    assert result.trades[0]["reason"] == "stop_loss"


def test_gap_down_stop_uses_open_price() -> None:
    data = bars()
    data[2].update({"open": 95.0, "high": 96.0, "low": 94.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG")]))
    assert result.trades[0]["exit"] == 95.0


def test_partial_take_profit_creates_first_leg() -> None:
    data = bars()
    data[2].update({"high": 102.0, "close": 101.5})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG")]), partial_take_profit=True)
    assert result.trades[0]["reason"] == "partial_take_profit"
    assert result.trades[0]["qty"] == pytest.approx(25.0)


def test_partial_take_profit_moves_remaining_stop_to_breakeven() -> None:
    data = bars()
    data[2].update({"high": 102.0, "close": 101.5})
    data[3].update({"low": 99.9, "close": 100.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("LONG")]), partial_take_profit=True)
    assert len(result.trades) == 2
    assert result.trades[1]["reason"] == "stop_loss"
    assert result.trades[1]["exit"] == pytest.approx(100.0)


def test_short_stop_is_conservative() -> None:
    data = bars()
    data[2].update({"high": 105.0, "low": 95.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, ScriptedStrategy([signal("SHORT")]))
    assert result.trades[0]["reason"] == "stop_loss"


def test_no_signal_creates_no_trade() -> None:
    result = BacktestEngine().run(bars(), ScriptedStrategy([signal("NEUTRAL")]))
    assert result.total_trades == 0


def test_net_equity_curve_present() -> None:
    result = BacktestEngine().run(bars(), ScriptedStrategy([signal("LONG")]))
    assert result.net_equity_curve is not None
    assert len(result.net_equity_curve) == len(result.equity_curve)


def test_custom_zero_costs_keep_flat_result_flat() -> None:
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(bars(), ScriptedStrategy([signal("LONG")]))
    assert result.net_total_return_pct == pytest.approx(0.0)
    assert result.fees_paid == 0.0


def test_invalid_costs_rejected() -> None:
    with pytest.raises(ValueError):
        BacktestEngine(fee_rate=-0.1)
    with pytest.raises(ValueError):
        BacktestEngine(slippage_pct=-0.1)


def test_limit_expiry_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        BacktestEngine(limit_expiry_bars=0)
