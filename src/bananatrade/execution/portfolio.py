"""Pure in-memory portfolio accounting."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping


class UnknownPositionError(KeyError):
    """Raised when closing a symbol without an open position."""


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_fee: float = 0.0

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == "LONG" else -self.quantity


class Portfolio:
    def __init__(self, cash: float, fee_rate: float = 0.0, *, now=None):
        self.cash = float(cash)
        self.initial_cash = float(cash)
        self.fee_rate = float(fee_rate)
        self.positions: dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.peak_equity = float(cash)
        self.equity = float(cash)
        self.unrealized_pnl = 0.0
        self.drawdown = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
        self._utc_date = self._as_date(now)
        self._prices: dict[str, float] = {}

    @staticmethod
    def _as_date(value) -> date:
        if value is None:
            return datetime.now(timezone.utc).date()
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    def _reset_day(self, now=None):
        current = self._as_date(now)
        if current != self._utc_date:
            self._utc_date, self.trades_today = current, 0

    def _fee(self, price, quantity):
        return abs(float(price) * float(quantity)) * self.fee_rate

    def open_position(self, symbol, side, quantity, price, *, timestamp=None, fee=None):
        self._reset_day(timestamp)
        side = str(side).upper()
        if side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if symbol in self.positions:
            raise ValueError(f"position already open: {symbol}")
        quantity, price = float(quantity), float(price)
        charged = self._fee(price, quantity) if fee is None else float(fee)
        self.cash += (-price * quantity if side == "LONG" else price * quantity) - charged
        self.total_fees += charged
        self.positions[symbol] = Position(symbol, side, quantity, price, charged)
        self.trades_today += 1
        return self.positions[symbol]

    def close_position(self, symbol, price, *, timestamp=None, fee=None):
        self._reset_day(timestamp)
        if symbol not in self.positions:
            raise UnknownPositionError(symbol)
        position = self.positions.pop(symbol)
        price = float(price)
        charged = self._fee(price, position.quantity) if fee is None else float(fee)
        gross = (price - position.entry_price) * position.quantity * (1 if position.side == "LONG" else -1)
        net = gross - charged - position.entry_fee
        self.cash += gross - charged
        self.realized_pnl += net
        self.total_fees += charged
        self.trades_today += 1
        self.consecutive_losses = self.consecutive_losses + 1 if net < 0 else 0
        self.mark(self._prices)
        return net

    def mark(self, prices: Mapping[str, float]):
        self._prices = {str(k): float(v) for k, v in prices.items()}
        self.unrealized_pnl = sum((self._prices[p.symbol] - p.entry_price) * p.quantity * (1 if p.side == "LONG" else -1) for p in self.positions.values() if p.symbol in self._prices)
        self.equity = self.cash + sum(self._prices[p.symbol] * p.signed_quantity for p in self.positions.values() if p.symbol in self._prices)
        self.peak_equity = max(self.peak_equity, self.equity)
        self.drawdown = self.peak_equity - self.equity
        return self.equity

    def snapshot(self):
        return {"cash": self.cash, "equity": self.equity, "realized_pnl": self.realized_pnl, "unrealized_pnl": self.unrealized_pnl, "total_fees": self.total_fees, "peak_equity": self.peak_equity, "drawdown": self.drawdown, "trades_today": self.trades_today, "consecutive_losses": self.consecutive_losses, "positions": {k: {"side": v.side, "quantity": v.quantity, "entry_price": v.entry_price} for k, v in self.positions.items()}}
