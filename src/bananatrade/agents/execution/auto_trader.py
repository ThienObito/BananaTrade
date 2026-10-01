"""Autonomous paper-only signal execution."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, TypedDict

from ...paper_broker import PaperBroker


class AutoTradeDecision(TypedDict):
    """Result returned after one paper-trading decision."""

    action: Literal["BUY", "SELL", "NONE"]
    reason: str
    order_id: str | None


class AutoTrader:
    """Place at most one-unit paper orders from a validated signal."""

    def __init__(self, broker: PaperBroker, symbol: str = "BTC/USDT") -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        self.broker = broker
        self.symbol = symbol.strip()

    def run_once(
        self,
        state: Mapping[str, object],
        signal: Mapping[str, object],
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
        quantity: float = 1.0,
    ) -> AutoTradeDecision:
        """Evaluate one signal and place only paper market orders."""
        bias = signal.get("bias")
        if not isinstance(bias, str):
            return self._skip("invalid signal bias")
        normalized_bias = bias.strip().upper()
        if normalized_bias == "NEUTRAL":
            return self._skip("neutral signal")
        if signal.get("stale") is True:
            return self._skip("stale signal")
        if normalized_bias not in {"LONG", "SHORT"}:
            return self._skip("unsupported signal bias")

        net_position = self._net_position(state)
        if normalized_bias == "LONG" and net_position > 0:
            return self._skip("already long")
        if normalized_bias == "SHORT" and net_position < 0:
            return self._skip("already short")

        price = self._signal_price(signal)
        if price is None:
            return self._skip("signal price unavailable")
        side: Literal["BUY", "SELL"] = "BUY" if normalized_bias == "LONG" else "SELL"
        resolved_stop = stop_loss if stop_loss is not None else sl
        resolved_target = take_profit if take_profit is not None else tp
        fill = self.broker.submit_market(
            self.symbol,
            side,
            quantity,
            price,
            stop_loss=resolved_stop,
            take_profit=resolved_target,
        )
        return {"action": side, "reason": f"{normalized_bias} signal executed", "order_id": fill.order_id}

    @staticmethod
    def _skip(reason: str) -> AutoTradeDecision:
        return {"action": "NONE", "reason": reason, "order_id": None}

    def _net_position(self, state: Mapping[str, object]) -> float:
        positions = state.get("positions", state.get("open_positions", []))
        if isinstance(positions, Mapping):
            position = positions.get(self.symbol)
            return self._position_quantity(position)
        if not isinstance(positions, list):
            return 0.0
        total = 0.0
        for position in positions:
            if not isinstance(position, Mapping) or position.get("symbol") != self.symbol:
                continue
            total += self._position_quantity(position)
        return total

    @staticmethod
    def _position_quantity(position: object) -> float:
        if not isinstance(position, Mapping):
            return 0.0
        quantity = position.get("quantity", 0.0)
        return float(quantity) if isinstance(quantity, (int, float)) and not isinstance(quantity, bool) else 0.0

    @staticmethod
    def _signal_price(signal: Mapping[str, object]) -> float | None:
        for key in ("price", "last_price"):
            value = signal.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return float(value)
        candles = signal.get("candles")
        if isinstance(candles, list) and candles:
            last = candles[-1]
            if isinstance(last, Mapping):
                value = last.get("close")
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                    return float(value)
        return None
