import pytest

from bananatrade.paper_broker import PaperBroker


def test_state_after_opening_position() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "buy", 2.0, 100.0)

    state = broker.state({"BTC/USDT": 110.0})

    assert state["cash"] == pytest.approx(800.0)
    assert state["equity"] == pytest.approx(1_020.0)
    assert state["exposure"] == pytest.approx(220.0)
    assert state["drawdown"] == pytest.approx(0.0)
    assert state["open_positions"] == [
        {
            "symbol": "BTC/USDT",
            "quantity": 2.0,
            "average_price": 100.0,
            "realized_pnl": 0.0,
        }
    ]


def test_state_after_closing_position() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "buy", 2.0, 100.0)
    broker.submit_market("BTC/USDT", "sell", 2.0, 110.0)

    state = broker.state({"BTC/USDT": 110.0})

    assert state["cash"] == pytest.approx(1_020.0)
    assert state["equity"] == pytest.approx(1_020.0)
    assert state["open_positions"] == []
    assert state["exposure"] == pytest.approx(0.0)
    assert state["drawdown"] == pytest.approx(0.0)


def test_state_with_zero_positions() -> None:
    state = PaperBroker(1_000.0).state()

    assert state["equity"] == pytest.approx(1_000.0)
    assert state["cash"] == pytest.approx(1_000.0)
    assert state["open_positions"] == []
    assert state["positions"] == []
    assert state["open_orders"] == []
    assert state["exposure"] == pytest.approx(0.0)
    assert state["drawdown"] == pytest.approx(0.0)
    assert "side" not in state


def test_buy_fill_increases_position_quantity() -> None:
    broker = PaperBroker(1_000.0)

    broker.submit_market("BTC/USDT", "BUY", 2.0, 100.0)

    assert broker.positions["BTC/USDT"].quantity == pytest.approx(2.0)
    assert broker.fills[-1].side == "BUY"


def test_sell_fill_decreases_position_quantity() -> None:
    broker = PaperBroker(1_000.0)
    broker.submit_market("BTC/USDT", "BUY", 2.0, 100.0)

    broker.submit_market("BTC/USDT", "SELL", 0.75, 110.0)

    assert broker.positions["BTC/USDT"].quantity == pytest.approx(1.25)
    assert broker.fills[-1].side == "SELL"


def test_order_validation_rejects_invalid_symbol_side_qty_and_price() -> None:
    broker = PaperBroker(1_000.0)

    invalid_orders = [
        ("", "BUY", 1.0, 100.0, "symbol"),
        ("BTC/USDT", "HOLD", 1.0, 100.0, "side"),
        ("BTC/USDT", "BUY", 0.0, 100.0, "qty"),
        ("BTC/USDT", "BUY", 1.0, 0.0, "price"),
    ]
    for symbol, side, quantity, price, field in invalid_orders:
        with pytest.raises(ValueError, match=field):
            broker.submit_market(symbol, side, quantity, price)
