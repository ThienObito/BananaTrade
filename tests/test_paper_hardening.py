import pytest

from bananatrade.engine.position_sizer import PositionSizer
from bananatrade.paper_broker import PaperBroker


def test_broker_rejects_buy_above_cash() -> None:
    broker = PaperBroker(100.0)
    with pytest.raises(ValueError, match="insufficient cash"):
        broker.submit_market("BTC/USDT", "BUY", 2.0, 100.0)


def test_partial_sell_preserves_protective_metadata() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "BUY", 2.0, 100.0, stop_loss=90.0, take_profit=120.0)
    broker.submit_market("BTC/USDT", "SELL", 1.0, 110.0)
    position = broker.positions["BTC/USDT"]
    assert position.stop_loss == 90.0
    assert position.take_profit == 120.0


def test_position_sizer_rejects_zero_equity() -> None:
    with pytest.raises(ValueError):
        PositionSizer.compute_qty(0.0, 100.0, 90.0)


def test_position_sizer_rejects_risk_above_one() -> None:
    with pytest.raises(ValueError):
        PositionSizer.compute_qty(1000.0, 100.0, 90.0, 1.1)
