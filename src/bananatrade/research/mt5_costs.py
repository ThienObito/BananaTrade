"""Historical MT5 spread, commission, and slippage cost model."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class MT5CostModel:
    """Apply per-bar spread points and market-fill costs.

    Historical OHLC values represent a mid/reference price. Market fills use
    half spread on the adverse side plus configured point slippage. Quantity is
    treated as lots for commission calculation, matching research sizing units.
    """

    point: float
    commission_per_lot: float = 0.0
    slippage_points: float = 1.0

    def __post_init__(self) -> None:
        if not isfinite(self.point) or self.point <= 0:
            raise ValueError("point must be positive and finite")
        if not isfinite(self.commission_per_lot) or self.commission_per_lot < 0:
            raise ValueError("commission_per_lot must be non-negative and finite")
        if not isfinite(self.slippage_points) or self.slippage_points < 0:
            raise ValueError("slippage_points must be non-negative and finite")

    def spread_price(self, candle: dict[str, float]) -> float:
        """Convert per-bar MT5 spread points to price distance."""
        spread = candle.get("spread", 0.0)
        if not isinstance(spread, (int, float)) or isinstance(spread, bool) or not isfinite(spread) or spread < 0:
            raise ValueError("candle spread must be non-negative and finite")
        return spread * self.point

    def slippage_price(self) -> float:
        """Return configured adverse market slippage in price units."""
        return self.slippage_points * self.point

    def market_fill(self, price: float, side: str, opening: bool, candle: dict[str, float]) -> float:
        """Return conservative market fill around reference price."""
        return self._fill(price, side, opening, candle, self.slippage_price())

    def limit_fill(self, price: float, side: str, opening: bool, candle: dict[str, float]) -> float:
        """Return hard-limit fill; requested price caps adverse execution."""
        if side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if not isfinite(price) or price <= 0:
            raise ValueError("price must be positive and finite")
        self.spread_price(candle)
        if not opening:
            return self._fill(price, side, opening, candle, 0.0)
        if side == "LONG":
            return price
        return price

    def _fill(self, price: float, side: str, opening: bool, candle: dict[str, float], slippage: float) -> float:
        if side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if not isfinite(price) or price <= 0:
            raise ValueError("price must be positive and finite")
        half_spread = self.spread_price(candle) / 2.0
        adverse = half_spread + slippage
        long_fill = price + adverse if opening else price - adverse
        short_fill = price - adverse if opening else price + adverse
        return long_fill if side == "LONG" else short_fill

    def spread_cost(self, quantity: float, candle: dict[str, float], fills: int = 1) -> float:
        """Return spread component paid across one or more market fills."""
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not isfinite(quantity) or quantity < 0 or not isinstance(fills, int) or isinstance(fills, bool) or fills < 0:
            raise ValueError("quantity and fills must be non-negative finite values")
        return self.spread_price(candle) / 2.0 * quantity * fills

    def slippage_cost(self, quantity: float, fills: int = 1) -> float:
        """Return point-slippage component paid across market fills."""
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not isfinite(quantity) or quantity < 0 or not isinstance(fills, int) or isinstance(fills, bool) or fills < 0:
            raise ValueError("quantity and fills must be non-negative finite values")
        return self.slippage_price() * quantity * fills

    def commission(self, quantity: float, fills: int = 1) -> float:
        """Return commission for quantity in lots across fills."""
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not isfinite(quantity) or quantity < 0 or not isinstance(fills, int) or isinstance(fills, bool) or fills < 0:
            raise ValueError("quantity and fills must be non-negative finite values")
        return self.commission_per_lot * quantity * fills


def cost_model_from_row(symbol_point: float, commission_per_lot: float, row: dict[str, object]) -> MT5CostModel:
    """Build model from symbol point, row slippage, and commission setting."""
    slippage_points = row.get("slippage_points", 1.0)
    if not isinstance(slippage_points, (int, float)) or isinstance(slippage_points, bool):
        raise TypeError("slippage_points must be numeric")
    return MT5CostModel(symbol_point, commission_per_lot, slippage_points=float(slippage_points))
