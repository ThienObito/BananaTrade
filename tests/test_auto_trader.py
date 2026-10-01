from bananatrade.agents.execution.auto_trader import AutoTrader
from bananatrade.paper_broker import PaperBroker


def signal(bias: str, *, stale: bool = False, price: float = 100.0) -> dict[str, object]:
    return {"bias": bias, "stale": stale, "price": price}


def test_long_signal_with_flat_position_places_buy() -> None:
    broker = PaperBroker(1_000.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("LONG", price=101.0))

    assert decision["action"] == "BUY"
    assert decision["order_id"] == "paper-1"
    assert broker.positions["BTC/USDT"].quantity == 1.0


def test_short_signal_with_flat_position_places_sell() -> None:
    broker = PaperBroker(1_000.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("SHORT", price=101.0))

    assert decision["action"] == "SELL"
    assert decision["order_id"] == "paper-1"
    assert broker.positions["BTC/USDT"].quantity == -1.0


def test_neutral_signal_places_nothing() -> None:
    broker = PaperBroker(1_000.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("NEUTRAL"))

    assert decision == {"action": "NONE", "reason": "neutral signal", "order_id": None}
    assert broker.fills == []


def test_stale_signal_places_nothing() -> None:
    broker = PaperBroker(1_000.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("LONG", stale=True))

    assert decision == {"action": "NONE", "reason": "stale signal", "order_id": None}
    assert broker.fills == []


def test_already_long_skips_buy() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "BUY", 1.0, 100.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("LONG"))

    assert decision == {"action": "NONE", "reason": "already long", "order_id": None}
    assert len(broker.fills) == 1


def test_already_short_skips_sell() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "SELL", 1.0, 100.0)
    trader = AutoTrader(broker)

    decision = trader.run_once(broker.state(), signal("SHORT"))

    assert decision == {"action": "NONE", "reason": "already short", "order_id": None}
    assert len(broker.fills) == 1
