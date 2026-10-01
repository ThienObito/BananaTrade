"""Pure paper-trading order-ticket prefill calculations.

The module deliberately contains no exchange or network calls. The web server can
wire :func:`post_order_prefill` to ``POST /api/order/prefill`` and provide the
latest serialized market snapshot in the request payload.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Protocol, TypedDict

STOP_ATR_MULTIPLIER = 1.5
TARGET_ATR_MULTIPLIER = 3.15
ORDER_PREFILL_PATH = "/api/order/prefill"


class SnapshotObject(Protocol):
    """Minimal protocol for snapshot models that can be serialized."""

    def to_compact_dict(self, precision: int = 6) -> dict[str, Any]:
        """Return a JSON-compatible snapshot mapping."""


SnapshotInput = Mapping[str, Any] | SnapshotObject


class OrderPrefill(TypedDict):
    """JSON response returned by the order-prefill endpoint."""

    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    reward: float
    risk: float
    reward_risk: float


_MISSING = object()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be an object")
    return value


def _snapshot_mapping(snapshot: SnapshotInput) -> Mapping[str, Any]:
    if isinstance(snapshot, Mapping):
        return snapshot
    return _mapping(snapshot.to_compact_dict(), "snapshot")


def _number(value: Any, field: str) -> float:
    if value is _MISSING or value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _positive_number(value: Any, field: str) -> float:
    result = _number(value, field)
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _optional_number(value: Any, field: str) -> float | None:
    if value is _MISSING or value is None:
        return None
    return _number(value, field)


def _normal_side(side: Any) -> str:
    if not isinstance(side, str):
        raise TypeError("side must be LONG, SHORT, buy, or sell")
    normalized = side.strip().upper()
    normalized = {"BUY": "LONG", "SELL": "SHORT"}.get(normalized, normalized)
    if normalized not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG, SHORT, buy, or sell")
    return normalized


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _snapshot_levels(snapshot: Mapping[str, Any]) -> tuple[float, float, Mapping[str, Any]]:
    timeframes = _mapping(snapshot.get("timeframes", _MISSING), "snapshot.timeframes")
    one_hour = _mapping(timeframes.get("1h", _MISSING), "snapshot.timeframes.1h")
    entry = _positive_number(
        one_hour.get("last_price", _MISSING),
        "snapshot.timeframes.1h.last_price",
    )
    indicators = _mapping(
        one_hour.get("indicators", _MISSING),
        "snapshot.timeframes.1h.indicators",
    )
    atr = _positive_number(indicators.get("atr", _MISSING), "snapshot.timeframes.1h.indicators.atr")
    return entry, atr, indicators


def prefill_order(symbol: str, side: str, snapshot: SnapshotInput) -> OrderPrefill:
    """Build deterministic paper order levels from a market snapshot.

    Existing side-specific ``atr_stop_<side>`` and ``atr_target_<side>`` values
    take precedence. Missing levels are calculated from ATR using 1.5 ATR for
    risk and 3.15 ATR for reward.
    """
    normalized_symbol = _required_text(symbol, "symbol")
    normalized_side = _normal_side(side)
    snapshot_data = _snapshot_mapping(snapshot)
    entry, atr, indicators = _snapshot_levels(snapshot_data)

    suffix = normalized_side.casefold()
    stop = _optional_number(indicators.get(f"atr_stop_{suffix}", _MISSING), f"atr_stop_{suffix}")
    target = _optional_number(
        indicators.get(f"atr_target_{suffix}", _MISSING),
        f"atr_target_{suffix}",
    )
    if stop is None:
        stop = (
            entry - STOP_ATR_MULTIPLIER * atr
            if normalized_side == "LONG"
            else entry + STOP_ATR_MULTIPLIER * atr
        )
    if target is None:
        target = (
            entry + TARGET_ATR_MULTIPLIER * atr
            if normalized_side == "LONG"
            else entry - TARGET_ATR_MULTIPLIER * atr
        )

    if stop <= 0 or target <= 0:
        raise ValueError("stop and target must be positive")
    if normalized_side == "LONG" and (stop >= entry or target <= entry):
        raise ValueError("LONG stop must be below entry and target above entry")
    if normalized_side == "SHORT" and (stop <= entry or target >= entry):
        raise ValueError("SHORT stop must be above entry and target below entry")

    risk = abs(entry - stop)
    reward = target - entry if normalized_side == "LONG" else entry - target
    if risk <= 0:
        raise ValueError("stop must differ from entry")
    if reward <= 0:
        raise ValueError("target must provide positive reward")

    return {
        "symbol": normalized_symbol,
        "side": normalized_side,
        "entry": entry,
        "stop": stop,
        "target": target,
        "reward": reward,
        "risk": risk,
        "reward_risk": reward / risk,
    }


def post_order_prefill(payload: Mapping[str, Any]) -> OrderPrefill:
    """Process a JSON body for ``POST /api/order/prefill``."""
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be an object")
    symbol = _required_text(payload.get("symbol", _MISSING), "symbol")
    side = _required_text(payload.get("side", _MISSING), "side")
    snapshot_value = payload.get("snapshot", _MISSING)
    if not isinstance(snapshot_value, Mapping) and not hasattr(snapshot_value, "to_compact_dict"):
        raise ValueError("snapshot must be an object")
    return prefill_order(symbol, side, snapshot_value)


# Explicit endpoint-oriented alias for integrations that prefer a handler name.
handle_order_prefill = post_order_prefill
