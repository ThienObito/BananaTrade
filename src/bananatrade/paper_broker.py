"""Deterministic in-memory paper broker with immediate market fills."""
from dataclasses import dataclass
from itertools import count
from math import isfinite

from .risk import RiskEngine


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float

@dataclass
class Position:
    quantity: float = 0.0
    average_price: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None


class PaperBroker:
    def __init__(self, cash: float, risk: RiskEngine | None = None, fee_rate: float = 0.0) -> None:
        if cash <= 0: raise ValueError("cash must be positive")
        self.cash, self.initial_cash, self.fee_rate = cash, cash, fee_rate
        self.risk = risk
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self._ids = count(1)

    def submit_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        **risk_state: float,
    ) -> Fill:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(side, str) or side.upper() not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not isfinite(quantity) or quantity <= 0:
            raise ValueError("qty must be greater than 0")
        if not isinstance(price, (int, float)) or isinstance(price, bool) or not isfinite(price) or price <= 0:
            raise ValueError("price must be greater than 0")
        normalized_side = side.upper()
        signed = quantity if normalized_side == "BUY" else -quantity
        symbol = symbol.strip()
        current = self.positions.get(symbol, Position())
        if self.risk:
            self.risk.approve(
                equity=self.equity({symbol: price}),
                position_notional=(current.quantity + signed) * price,
                total_exposure=sum(
                    abs(p.quantity * risk_state.get("price", price))
                    for p in self.positions.values()
                ),
                **risk_state,
            )
        fee = quantity * price * self.fee_rate
        if normalized_side == "BUY" and current.quantity >= 0 and self.cash < quantity * price + fee:
            raise ValueError("insufficient cash for BUY")
        self.cash -= signed * price + fee
        pos = self.positions.setdefault(symbol, Position())
        old, new = pos.quantity, pos.quantity + signed
        if old and old * signed < 0:
            closed = min(abs(old), abs(signed)); pos.realized_pnl += closed * (price - pos.average_price) * (1 if old > 0 else -1)
        if new == 0: pos.average_price = 0.0
        elif old == 0 or old * signed >= 0: pos.average_price = (abs(old) * pos.average_price + abs(signed) * price) / abs(new)
        elif old * new < 0: pos.average_price = price
        pos.quantity = new
        if new != 0:
            if stop_loss is not None:
                pos.stop_loss = stop_loss
            if take_profit is not None:
                pos.take_profit = take_profit
        else:
            pos.stop_loss = None
            pos.take_profit = None
        fill = Fill(f"paper-{next(self._ids)}", symbol.strip(), normalized_side, quantity, price, fee)
        self.fills.append(fill)
        return fill

    def equity(self, marks: dict[str, float] | None = None) -> float:
        marks = marks or {}
        return self.cash + sum(p.quantity * marks.get(s, p.average_price) for s, p in self.positions.items())

    def unrealized_pnl(self, marks: dict[str, float]) -> float:
        return sum(p.quantity * (marks[s] - p.average_price) for s, p in self.positions.items() if s in marks)

    def state(self, marks: dict[str, float] | None = None) -> dict[str, object]:
        """Return the broker's canonical account snapshot.

        ``marks`` contains the latest prices used to value open positions.  When
        a mark is unavailable, the position's average entry price is used so
        this method remains deterministic for an unmarked account.
        """
        marks = marks or {}
        equity = self.equity(marks)
        open_positions = [
            {
                "symbol": symbol,
                "quantity": position.quantity,
                "average_price": position.average_price,
                "realized_pnl": position.realized_pnl,
                **({"stop_loss": position.stop_loss} if position.stop_loss is not None else {}),
                **({"take_profit": position.take_profit} if position.take_profit is not None else {}),
            }
            for symbol, position in self.positions.items()
            if position.quantity != 0
        ]
        exposure = sum(
            abs(position.quantity * marks.get(symbol, position.average_price))
            for symbol, position in self.positions.items()
            if position.quantity != 0
        )
        peak_equity = max(self.initial_cash, equity)
        drawdown = (peak_equity - equity) / peak_equity if peak_equity else 0.0
        return {
            "equity": equity,
            "cash": self.cash,
            "open_positions": open_positions,
            "positions": open_positions,
            "open_orders": [],
            "exposure": exposure,
            "drawdown": drawdown,
        }
