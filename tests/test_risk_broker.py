from pathlib import Path

import pytest

from bananatrade.paper_broker import PaperBroker
from bananatrade.risk import RiskConfig, RiskEngine, RiskRejected

ROOT = Path(__file__).parents[1]

def test_config_loads_yaml():
    c = RiskConfig.from_yaml(ROOT / "config" / "risk.yaml")
    assert c.max_position_pct == .10
    assert c.max_trades_per_day == 5

def test_risk_rejects_missing_stop_loss_before_arithmetic():
    engine = RiskEngine()
    result = engine.check(equity=1000, position_notional=10, total_exposure=10, entry=100, take_profit=120)
    assert not result.approved
    assert result.reason == "missing proposal field: stop_loss"


def test_risk_rejects_missing_take_profit_before_arithmetic():
    engine = RiskEngine()
    result = engine.check(equity=1000, position_notional=10, total_exposure=10, entry=100, stop_loss=90)
    assert not result.approved
    assert result.reason == "missing proposal field: take_profit"


def test_risk_accepts_valid_proposal():
    engine = RiskEngine()
    result = engine.check(equity=1000, position_notional=10, total_exposure=10, entry=100, stop_loss=90, take_profit=120)
    assert result.approved


def test_risk_rejects_position_limit():
    engine = RiskEngine(RiskConfig(max_position_pct=.1))
    result = engine.check(equity=1000, position_notional=101, total_exposure=101)
    assert not result.approved
    assert result.reason == "max position exceeded"
    with pytest.raises(RiskRejected, match="max position"):
        engine.approve(equity=1000, position_notional=101, total_exposure=101)

def test_long_and_short_pnl():
    broker = PaperBroker(10_000)
    broker.submit_market("BTC", "buy", 2, 100)
    assert broker.unrealized_pnl({"BTC": 110}) == 20
    broker.submit_market("BTC", "sell", 2, 110)
    assert broker.positions["BTC"].realized_pnl == 20
    broker.submit_market("ETH", "sell", 2, 100)
    assert broker.unrealized_pnl({"ETH": 90}) == 20
    broker.submit_market("ETH", "buy", 2, 90)
    assert broker.positions["ETH"].realized_pnl == 20

def test_fee_and_invalid_order():
    broker = PaperBroker(1000, fee_rate=.001)
    broker.submit_market("BTC", "buy", 1, 100)
    assert broker.cash == pytest.approx(899.9)
    with pytest.raises(ValueError):
        broker.submit_market("BTC", "buy", 0, 100)
