from __future__ import annotations

from typing import Literal

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.engine.strategy import SignalResult
from bananatrade.research.mt5_costs import MT5CostModel


class OneShot:
    def __init__(self, bias: Literal["LONG", "SHORT"] = "LONG", entry_mode: Literal["market", "limit"] = "market") -> None:
        self.bias = bias
        self.entry_mode = entry_mode
        self.calls = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        if self.calls:
            return SignalResult("NEUTRAL", 0.0, "done")
        self.calls += 1
        limit = 99.0 if self.entry_mode == "limit" else None
        return SignalResult(self.bias, 1.0, "one shot", self.entry_mode, limit)


def bars() -> list[dict[str, object]]:
    return [
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "spread": 4.0, "atr14": 1.0, "volume": 1.0},
        {"open": 100.0, "high": 104.0, "low": 99.0, "close": 103.0, "spread": 6.0, "atr14": 1.0, "volume": 1.0},
        {"open": 103.0, "high": 103.0, "low": 103.0, "close": 103.0, "spread": 2.0, "atr14": 1.0, "volume": 1.0},
    ]


def model() -> MT5CostModel:
    return MT5CostModel(point=0.01, commission_per_lot=2.0, slippage_points=1.0)


def test_market_trade_reconciles_aggregate_costs() -> None:
    result = BacktestEngine(fee_rate=0.0, cost_model=model()).run(bars(), OneShot())
    trade = result.trades[0]
    assert result.total_trades == 1
    assert result.spread_cost_paid == pytest.approx(float(trade["spread_cost"]))
    assert result.commission_paid == pytest.approx(float(trade["commission_cost"]))
    assert float(trade["slippage_cost"]) == pytest.approx(0.48)
    assert float(trade["net_pnl"]) < float(trade["gross_pnl"])


def test_limit_entry_has_no_entry_market_slippage() -> None:
    data = bars()
    data[1]["low"] = 98.5
    result = BacktestEngine(fee_rate=0.0, cost_model=model()).run(data, OneShot(entry_mode="limit"))
    trade = result.trades[0]
    assert float(trade["entry_slippage"]) == 0.0
    assert float(trade["slippage_cost"]) == pytest.approx(float(trade["qty"]) * model().slippage_price())


def test_missing_spread_rejected_in_mt5_mode() -> None:
    data = bars()
    del data[0]["spread"]
    with pytest.raises(ValueError, match="spread"):
        BacktestEngine(cost_model=model()).run(data, OneShot())


def test_legacy_mode_keeps_missing_spread_compatible() -> None:
    data = bars()
    del data[0]["spread"]
    result = BacktestEngine().run(data, OneShot())
    assert result.total_trades == 1


def test_mark_to_market_does_not_mutate_cost_totals() -> None:
    data = bars() + bars() + bars()
    result = BacktestEngine(fee_rate=0.0, cost_model=model()).run(data, OneShot())
    trade = result.trades[0]
    assert result.spread_cost_paid == pytest.approx(float(trade["spread_cost"]))
    assert result.commission_paid == pytest.approx(float(trade["commission_cost"]))


def test_short_market_costs_are_adverse() -> None:
    result = BacktestEngine(fee_rate=0.0, cost_model=model()).run(bars(), OneShot("SHORT"))
    trade = result.trades[0]
    assert float(trade["entry_fill"]) < float(trade["entry"])
    assert float(trade["exit_fill"]) > float(trade["exit"])


def test_partial_exit_allocates_entry_costs_once() -> None:
    data = bars()
    data[1]["high"] = 105.0
    result = BacktestEngine(fee_rate=0.0, cost_model=model()).run(data, OneShot(), partial_take_profit=True)
    assert result.total_trades >= 1
    assert result.spread_cost_paid == pytest.approx(sum(float(item["spread_cost"]) for item in result.trades))
    assert result.commission_paid == pytest.approx(sum(float(item["commission_cost"]) for item in result.trades))
