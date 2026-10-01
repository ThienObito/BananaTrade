"""Pure order-fill and exit-trigger simulation helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _side(value: Any) -> str:
    return str(_get(value, "side", "direction", default="")).lower()


def entry_fill(order: Any, next_bar: Any, slippage_bps: float, fee_bps: float) -> dict[str, Any] | None:
    """Fill an order at the next bar's open, applying adverse slippage and fees.

    An order is not filled when the bar closed before the order was submitted.
    The returned mapping contains the execution price and fee, plus order metadata.
    """
    order_time = _get(order, "time", "timestamp", "created_at", "order_time")
    bar_close = _get(next_bar, "close_time", "end_time", "timestamp", "time")
    if order_time is not None and bar_close is not None:
        try:
            if bar_close < order_time:
                return None
        except TypeError:
            pass

    side = _side(order)
    open_price = float(_get(next_bar, "open", "open_price"))
    factor = float(slippage_bps) / 10_000
    if side in ("buy", "long"):
        price = open_price * (1 + factor)
    elif side in ("sell", "short"):
        price = open_price * (1 - factor)
    else:
        raise ValueError(f"unsupported order side: {side!r}")

    quantity = _get(order, "quantity", "qty", "size", default=1)
    fee = abs(price * float(quantity)) * float(fee_bps) / 10_000
    return {
        "price": price,
        "fill_price": price,
        "fee": fee,
        "quantity": quantity,
        "side": side,
        "time": bar_close,
    }


def exit_check(position: Any, bar: Any) -> str | None:
    """Return the first exit trigger for *position* on *bar*.

    Stops take precedence when both stop and target are touched.  A gap through
    a stop is detected from the bar open as well as from the intrabar low/high.
    """
    side = _side(position)
    stop = _get(position, "stop_loss", "stop", "stop_price")
    target = _get(position, "take_profit", "target", "take_profit_price")
    if stop is None and target is None:
        return None
    op = float(_get(bar, "open", "open_price"))
    high = float(_get(bar, "high"))
    low = float(_get(bar, "low"))

    if side in ("buy", "long"):
        stopped = stop is not None and (op <= float(stop) or low <= float(stop))
        targeted = target is not None and high >= float(target)
    elif side in ("sell", "short"):
        stopped = stop is not None and (op >= float(stop) or high >= float(stop))
        targeted = target is not None and low <= float(target)
    else:
        raise ValueError(f"unsupported position side: {side!r}")
    if stopped:
        return "stop_loss"
    if targeted:
        return "take_profit"
    return None
