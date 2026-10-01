from __future__ import annotations

import pytest

from bananatrade.research.mt5_costs import MT5CostModel


@pytest.fixture
def model() -> MT5CostModel:
    return MT5CostModel(point=0.01, commission_per_lot=3.5, slippage_points=1.0)


def row(spread: float = 4.0) -> dict[str, float]:
    return {"spread": spread}


def test_spread_points_convert_to_price(model: MT5CostModel) -> None:
    assert model.spread_price(row()) == pytest.approx(0.04)


def test_market_long_entry_is_adverse(model: MT5CostModel) -> None:
    assert model.market_fill(100.0, "LONG", True, row()) == pytest.approx(100.03)


def test_market_long_exit_is_adverse(model: MT5CostModel) -> None:
    assert model.market_fill(100.0, "LONG", False, row()) == pytest.approx(99.97)


def test_market_short_entry_is_adverse(model: MT5CostModel) -> None:
    assert model.market_fill(100.0, "SHORT", True, row()) == pytest.approx(99.97)


def test_market_short_exit_is_adverse(model: MT5CostModel) -> None:
    assert model.market_fill(100.0, "SHORT", False, row()) == pytest.approx(100.03)


def test_slippage_cost_is_one_point_per_fill(model: MT5CostModel) -> None:
    assert model.slippage_cost(2.0, fills=2) == pytest.approx(0.04)


def test_commission_is_per_lot_per_fill(model: MT5CostModel) -> None:
    assert model.commission(2.0, fills=2) == pytest.approx(14.0)


def test_spread_cost_is_half_spread_per_fill(model: MT5CostModel) -> None:
    assert model.spread_cost(2.0, row(), fills=2) == pytest.approx(0.08)


def test_negative_spread_rejected(model: MT5CostModel) -> None:
    with pytest.raises(ValueError, match="spread"):
        model.spread_price(row(-1.0))


def test_default_commission_is_zero() -> None:
    assert MT5CostModel(0.00001).commission(1.0) == 0.0


def test_invalid_spread_and_fill_inputs_rejected(model: MT5CostModel) -> None:
    with pytest.raises(ValueError):
        model.spread_price({"spread": True})
    with pytest.raises(ValueError):
        model.spread_price({"spread": float("nan")})
    with pytest.raises(ValueError):
        model.commission(float("inf"))
    with pytest.raises(ValueError):
        model.commission(1.0, fills=True)
