"""Paper-position stop, partial take-profit, and trailing management."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypedDict


class CloseAction(TypedDict):
    """Instruction to close one paper position."""

    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    reason: str
    price: float


@dataclass(frozen=True)
class PartialExit:
    """One partial take-profit instruction."""

    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float
    reason: str


class ExitManager:
    """Check paper positions and maintain protective stop levels."""

    def check_exits(
        self,
        positions: list[dict[str, object]] | Mapping[str, dict[str, object]],
        current_price: float,
    ) -> list[CloseAction]:
        """Return close actions for positions whose SL or TP has been reached."""
        if current_price <= 0:
            raise ValueError("current_price must be positive")
        actions: list[CloseAction] = []
        for symbol, position in self._iter_positions(positions):
            quantity = self._signed_quantity(position)
            entry = self._first_number(position, "entry", "entry_price", "average_price")
            stop = self._first_number(position, "stop_loss", "sl", "stop")
            target = self._first_number(position, "take_profit", "tp", "target")
            if quantity == 0 or entry <= 0:
                continue
            if quantity > 0:
                risk = entry - stop
                if stop > 0 and current_price <= stop:
                    actions.append({"symbol": symbol, "side": "SELL", "quantity": abs(quantity), "reason": "stop_loss", "price": current_price})
                elif target > 0 and current_price >= target:
                    actions.append({"symbol": symbol, "side": "SELL", "quantity": abs(quantity), "reason": "take_profit", "price": current_price})
                elif risk > 0 and current_price - entry >= risk:
                    new_stop = entry if current_price - entry < 2 * risk else current_price - 2 * risk
                    position["stop_loss"] = max(stop, new_stop)
            else:
                risk = stop - entry
                if stop > 0 and current_price >= stop:
                    actions.append({"symbol": symbol, "side": "BUY", "quantity": abs(quantity), "reason": "stop_loss", "price": current_price})
                elif target > 0 and current_price <= target:
                    actions.append({"symbol": symbol, "side": "BUY", "quantity": abs(quantity), "reason": "take_profit", "price": current_price})
                elif risk > 0 and entry - current_price >= risk:
                    new_stop = entry if entry - current_price < 2 * risk else current_price + 2 * risk
                    position["stop_loss"] = min(stop, new_stop)
        return actions

    def partial_take_profit(
        self,
        position: dict[str, object],
        current_price: float,
    ) -> PartialExit | None:
        """Take 50% at 1.5R, move SL to breakeven, then trail remainder at 1R."""
        if current_price <= 0:
            raise ValueError("current_price must be positive")
        quantity = self._signed_quantity(position)
        entry = self._first_number(position, "entry", "entry_price", "average_price")
        atr14 = self._first_number(position, "atr14", "atr")
        if quantity == 0 or entry <= 0 or atr14 <= 0:
            return None
        long = quantity > 0
        tp1 = entry + 1.5 * atr14 if long else entry - 1.5 * atr14
        if not bool(position.get("partial_tp_hit", position.get("tp1_hit", False))):
            reached = current_price >= tp1 if long else current_price <= tp1
            if not reached:
                return None
            partial_quantity = abs(quantity) * 0.5
            initial_stop = self._first_number(position, "stop_loss", "sl", "stop")
            initial_risk = abs(entry - initial_stop) if initial_stop > 0 else atr14
            position["quantity"] = abs(quantity) * 0.5 * (1 if long else -1)
            position["partial_tp_hit"] = True
            position["tp1_hit"] = True
            position["initial_risk"] = initial_risk
            position["stop_loss"] = entry
            return PartialExit(
                str(position.get("symbol", "")),
                "SELL" if long else "BUY",
                partial_quantity,
                current_price,
                "partial_take_profit",
            )
        initial_risk = self._first_number(position, "initial_risk") or atr14
        trail = current_price - initial_risk if long else current_price + initial_risk
        stop = self._first_number(position, "stop_loss", "sl", "stop")
        improved = trail > stop if long else stop == 0 or trail < stop
        if improved:
            position["stop_loss"] = trail
        return None

    @staticmethod
    def _iter_positions(
        positions: list[dict[str, object]] | Mapping[str, dict[str, object]],
    ) -> list[tuple[str, dict[str, object]]]:
        if isinstance(positions, Mapping):
            return [(str(symbol), position) for symbol, position in positions.items()]
        result: list[tuple[str, dict[str, object]]] = []
        for position in positions:
            symbol = position.get("symbol")
            if isinstance(symbol, str):
                result.append((symbol, position))
        return result

    @classmethod
    def _signed_quantity(cls, position: Mapping[str, object]) -> float:
        quantity = cls._first_number(position, "quantity", "qty", "size")
        side = position.get("side")
        if isinstance(side, str) and side.strip().upper() in {"SELL", "SHORT"}:
            return -abs(quantity)
        return quantity

    @classmethod
    def _first_number(cls, position: Mapping[str, object], *keys: str) -> float:
        for key in keys:
            value = cls._number(position.get(key))
            if value != 0:
                return value
        return 0.0

    @staticmethod
    def _number(value: object) -> float:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
