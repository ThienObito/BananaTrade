from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from bananatrade import web_server
from bananatrade.agents.execution.auto_trader import AutoTrader
from bananatrade.engine.adaptive_trader import AdaptiveTrader
from bananatrade.engine.execution_model import ExecutionModel
from bananatrade.engine.regime_detector import Regime
from bananatrade.engine.strategy import SignalResult
from bananatrade.engine.trade_journal import TradeJournal
from bananatrade.paper_broker import PaperBroker
from bananatrade.risk_manager import RiskManager


def candle_data(price: float = 100.0, atr14: float = 2.0, count: int = 20) -> list[dict[str, object]]:
    return [{"open": price, "high": price + atr14, "low": price - atr14, "close": price, "atr14": atr14, "volume": 100.0} for _ in range(count)]


class FixedStrategy:
    def __init__(self, bias: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG", confidence: float = 0.9) -> None:
        self.bias = bias
        self.confidence = confidence

    def generate_signal(self, candles: Sequence[dict[str, object]]) -> SignalResult:
        return SignalResult(self.bias, self.confidence, "fixed")


def make_trader(tmp_path: Path, strategy: FixedStrategy | None = None) -> AdaptiveTrader:
    broker = PaperBroker(10_000.0)
    return AdaptiveTrader(
        AutoTrader(broker),
        risk_manager=RiskManager(),
        execution_model=ExecutionModel(10_000.0, 0.01),
        strategy=strategy,
        journal=TradeJournal(tmp_path / "journal.csv"),
    )


def test_execution_long_trending() -> None:
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.TRENDING)
    assert result is not None
    assert result.price == 100.0
    assert result.sl == pytest.approx(97.0)
    assert result.tp == pytest.approx(106.0)


def test_execution_long_ranging() -> None:
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.RANGING)
    assert result is not None
    assert result.sl == pytest.approx(98.0)
    assert result.tp == pytest.approx(104.0)


def test_execution_short_trending() -> None:
    result = ExecutionModel().compute_entry(SignalResult("SHORT", 0.9, "x"), candle_data(), Regime.TRENDING)
    assert result is not None
    assert result.sl == pytest.approx(103.0)
    assert result.tp == pytest.approx(94.0)


def test_execution_short_ranging() -> None:
    result = ExecutionModel().compute_entry(SignalResult("SHORT", 0.9, "x"), candle_data(), Regime.RANGING)
    assert result is not None
    assert result.sl == pytest.approx(102.0)
    assert result.tp == pytest.approx(96.0)


def test_execution_returns_none_volatile() -> None:
    assert ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.VOLATILE) is None


def test_execution_returns_none_neutral() -> None:
    assert ExecutionModel().compute_entry(SignalResult("NEUTRAL", 0.9, "x"), candle_data(), Regime.RANGING) is None


def test_execution_uses_current_close() -> None:
    data = candle_data(100.0)
    data[-1]["close"] = 110.0
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), data, Regime.RANGING)
    assert result is not None
    assert result.price == 110.0


def test_execution_uses_supplied_atr() -> None:
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(100, 4), Regime.TRENDING)
    assert result is not None
    assert result.sl == pytest.approx(94.0)


def test_execution_position_sizing() -> None:
    result = ExecutionModel(10_000.0, 0.01).compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.RANGING)
    assert result is not None
    assert result.qty == 50


def test_execution_custom_equity() -> None:
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.RANGING, equity=2_000.0)
    assert result is not None
    assert result.qty == 10


def test_execution_custom_risk() -> None:
    result = ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), candle_data(), Regime.RANGING, risk_pct=0.02)
    assert result is not None
    assert result.qty == 100


def test_execution_empty_candles_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), [], Regime.RANGING)


def test_execution_invalid_close_rejected() -> None:
    data = candle_data()
    data[-1]["close"] = 0
    with pytest.raises(ValueError, match="close"):
        ExecutionModel().compute_entry(SignalResult("LONG", 0.9, "x"), data, Regime.RANGING)


def test_execution_invalid_equity_rejected() -> None:
    with pytest.raises(ValueError, match="equity"):
        ExecutionModel(0.0)


def test_execution_invalid_risk_rejected() -> None:
    with pytest.raises(ValueError, match="risk_pct"):
        ExecutionModel(risk_pct=-0.1)


def test_adaptive_initial_status(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    status = trader.status()
    assert status["rolling_win_rate"] == 0.0
    assert status["consecutive_losses"] == 0
    assert status["effective_confidence_threshold"] == 0.65
    assert status["effective_risk_pct"] == 0.01


def test_adaptive_run_long(tmp_path: Path) -> None:
    trader = make_trader(tmp_path, FixedStrategy("LONG", 0.9))
    decision = trader.run_once(trader.broker.state(), candle_data(atr14=1.0))
    assert decision["action"] == "BUY"
    assert trader.last_signal is not None


def test_adaptive_volatile_skips(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    decision = trader.run_once(trader.broker.state(), candle_data())
    trader.regime_detector._last = trader.regime_detector.last_snapshot
    assert decision["action"] in {"BUY", "NONE"}


def test_adaptive_neutral_skips(tmp_path: Path) -> None:
    trader = make_trader(tmp_path, FixedStrategy("NEUTRAL", 0.9))
    decision = trader.run_once(trader.broker.state(), candle_data())
    assert decision["action"] == "NONE"


def test_adaptive_low_confidence_skips(tmp_path: Path) -> None:
    trader = make_trader(tmp_path, FixedStrategy("LONG", 0.5))
    decision = trader.run_once(trader.broker.state(), candle_data())
    assert decision["reason"] == "confidence below adaptive threshold"


def test_adaptive_records_journal(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    trader.run_once(trader.broker.state(), candle_data())
    assert (tmp_path / "journal.csv").exists()
    assert "ensemble" in (tmp_path / "journal.csv").read_text(encoding="utf-8")


def test_adaptive_rolling_win_rate(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for outcome in (True, False, True, True):
        trader.record_trade_result(outcome)
    assert trader.rolling_win_rate == 0.75


def test_adaptive_uses_last_20_results(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for _ in range(25):
        trader.record_trade_result(False)
    assert trader.rolling_win_rate == 0.0


def test_adaptive_raises_threshold_below_40_percent(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for outcome in (False, False, False, True, False):
        trader.record_trade_result(outcome)
    assert trader.rolling_win_rate < 0.40
    assert trader.effective_confidence_threshold == 0.75


def test_adaptive_keeps_threshold_at_40_percent(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for outcome in (True, True, False, False, True):
        trader.record_trade_result(outcome)
    assert trader.rolling_win_rate == 0.6
    assert trader.effective_confidence_threshold == 0.65


def test_adaptive_counts_consecutive_losses(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    trader.record_trade_result(False)
    trader.record_trade_result(False)
    trader.record_trade_result(False)
    assert trader.consecutive_losses == 3


def test_adaptive_halves_risk_after_three_losses(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for _ in range(3):
        trader.record_trade_result(False)
    assert trader.effective_risk_pct == pytest.approx(0.005)


def test_adaptive_win_resets_consecutive_losses(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    trader.record_trade_result(False)
    trader.record_trade_result(False)
    trader.record_trade_result(True)
    assert trader.consecutive_losses == 0


def test_adaptive_risk_restores_after_five_trades(tmp_path: Path) -> None:
    trader = make_trader(tmp_path)
    for _ in range(3):
        trader.record_trade_result(False)
    assert trader.effective_risk_pct == pytest.approx(0.005)
    for _ in range(5):
        trader.record_trade_result(True)
    assert trader.effective_risk_pct == pytest.approx(0.01)


def test_adaptive_status_after_run(tmp_path: Path) -> None:
    trader = make_trader(tmp_path, FixedStrategy("LONG", 0.9))
    trader.run_once(trader.broker.state(), candle_data(atr14=1.0))
    status = trader.status()
    assert status["regime"] is not None
    assert status["last_signal"] == "LONG"


def test_adaptive_custom_threshold(tmp_path: Path) -> None:
    trader = AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), journal=TradeJournal(tmp_path / "j.csv"), confidence_threshold=0.8)
    assert trader.effective_confidence_threshold == 0.8


def test_adaptive_invalid_threshold(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="confidence"):
        AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), journal=TradeJournal(tmp_path / "j.csv"), confidence_threshold=1.1)


def test_adaptive_invalid_risk(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="risk"):
        AdaptiveTrader(AutoTrader(PaperBroker(10_000.0)), journal=TradeJournal(tmp_path / "j.csv"), risk_pct=-0.1)


def test_adaptive_status_endpoint_schema() -> None:
    payload = web_server.adaptive_status()
    assert set(payload) == {"rolling_win_rate", "consecutive_losses", "effective_confidence_threshold", "effective_risk_pct", "regime", "last_signal", "pending_limit_orders", "partial_exits_today"}
