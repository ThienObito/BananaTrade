from typing import Literal

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.engine.strategy import SignalResult


class OneSignal:
    def __init__(self, bias: Literal["LONG", "SHORT"] = "LONG") -> None:
        self.bias = bias

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        return SignalResult(self.bias, 1.0, "exit fixture")


def bars(count: int = 40) -> list[dict[str, object]]:
    return [
        {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0, "atr14": 1.0}
        for _ in range(count)
    ]


def test_fixed_2r_hits_two_r_target() -> None:
    data = bars()
    data[2].update({"high": 103.1, "close": 102.5})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="fixed_2r", stop_atr_multiplier=1.5)
    assert result.trades[0]["reason"] == "take_profit"
    assert result.trades[0]["exit"] == pytest.approx(103.0)


def test_fixed_2r_has_initial_one_point_five_atr_stop() -> None:
    data = bars()
    data[2]["low"] = 98.4
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="fixed_2r", stop_atr_multiplier=1.5)
    assert result.trades[0]["reason"] == "stop_loss"
    assert result.trades[0]["exit"] == pytest.approx(98.5)


def test_atr_trailing_model_closes_on_trailing_stop() -> None:
    data = bars()
    data[2].update({"open": 100.0, "high": 104.0, "low": 100.0, "close": 103.5})
    data[3].update({"open": 103.0, "high": 103.5, "low": 102.1, "close": 102.2})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="atr_trailing_2x", stop_atr_multiplier=1.5)
    assert result.trades[0]["reason"] == "atr_trailing"


def test_atr_trailing_does_not_use_fixed_target() -> None:
    data = bars()
    data[2].update({"high": 103.0, "low": 99.0, "close": 102.0})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="atr_trailing_2x")
    assert result.trades[0]["reason"] != "take_profit"


def test_time_stop_closes_after_24_bars() -> None:
    data = bars(35)
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="time_stop_24")
    assert result.trades[0]["reason"] == "time_stop"


def test_time_stop_parameter_can_be_shortened() -> None:
    data = bars(15)
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="time_stop_24", time_stop_bars=5)
    assert result.trades[0]["reason"] == "time_stop"


def test_time_stop_checks_stop_before_time() -> None:
    data = bars(10)
    data[6]["low"] = 98.0
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal(), exit_model="time_stop_24", time_stop_bars=5)
    assert result.trades[0]["reason"] == "stop_loss"


def test_short_fixed_2r_target() -> None:
    data = bars()
    data[2].update({"low": 96.0, "close": 96.5})
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(data, OneSignal("SHORT"), exit_model="fixed_2r")
    assert result.trades[0]["reason"] == "take_profit"


def test_invalid_exit_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        BacktestEngine().run(bars(), OneSignal(), exit_model="bad")


def test_invalid_time_stop_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        BacktestEngine().run(bars(), OneSignal(), exit_model="time_stop_24", time_stop_bars=0)


def test_invalid_stop_multiplier_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        BacktestEngine().run(bars(), OneSignal(), exit_model="fixed_2r", stop_atr_multiplier=0.0)


def test_exit_model_is_recorded_on_trade() -> None:
    result = BacktestEngine(fee_rate=0.0, slippage_pct=0.0).run(bars(), OneSignal(), exit_model="time_stop_24", time_stop_bars=2)
    assert result.trades[0]["exit_model"] == "time_stop_24"
