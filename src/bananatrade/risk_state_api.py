"""Read-only risk-state data and the ``GET /api/risk/state`` handler.

The endpoint is deliberately independent of the trading transport.  A caller binds
an immutable mapping or a zero-argument state provider to the handler, and this
module turns that state into the small JSON payload required by the dashboard.
No order, exchange, network, or LLM operation is performed here.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler
from typing import ClassVar, TypedDict
from urllib.parse import urlsplit

from .risk import RiskConfig

RISK_STATE_PATH = "/api/risk/state"
_MISSING = object()


class RiskStateResponse(TypedDict):
    """JSON shape returned by the risk-state panel endpoint."""

    kill_switch: bool
    daily_pnl_pct: float
    exposure: float
    trades_today: int
    cooldown_active: bool
    last_rejection_reasons: list[str]


RiskStateSource = Mapping[str, object] | Callable[[], Mapping[str, object]]


def build_risk_state_response(
    state: Mapping[str, object] | None = None,
    *,
    risk_config: RiskConfig | None = None,
    **overrides: object,
) -> RiskStateResponse:
    """Build the JSON-ready state shown by the risk panel.

    ``daily_pnl_pct`` is expressed in percentage points (``1.25`` means
    ``+1.25%``).  Callers may provide it directly, or provide ``daily_pnl`` and
    positive ``equity`` and let this function calculate the percentage.  The
    cooldown is derived from ``consecutive_losses`` and ``RiskConfig`` unless an
    explicit ``cooldown_active`` value is supplied.

    The mapping accepts the canonical field names plus a few read-only state
    aliases used by risk engines: ``kill_switch_active``, ``total_exposure``,
    ``daily_trades``, ``last_rejections``, and ``rejection_reasons``.
    """
    data: dict[str, object] = dict(state or {})
    data.update(overrides)
    selected_config = risk_config or RiskConfig()

    kill_switch = _read_bool(
        _first(data, ("kill_switch", "kill_switch_active", "killed")),
        "kill_switch",
        default=False,
    )
    daily_pnl_pct = _read_daily_pnl_pct(data)
    exposure = _read_non_negative_number(
        _first(data, ("exposure", "total_exposure", "exposure_notional")),
        "exposure",
        default=0.0,
    )
    trades_today = _read_non_negative_integer(
        _first(data, ("trades_today", "daily_trades")),
        "trades_today",
        default=0,
    )
    cooldown_value = _first(data, ("cooldown_active", "cooldown"))
    if cooldown_value is _MISSING:
        consecutive_losses = _read_non_negative_integer(
            _first(data, ("consecutive_losses", "losses_in_a_row")),
            "consecutive_losses",
            default=0,
        )
        cooldown_active = consecutive_losses >= selected_config.cooldown_losses
    else:
        cooldown_active = _read_bool(cooldown_value, "cooldown_active")

    reasons = _read_rejection_reasons(
        _first(data, ("last_rejection_reasons", "last_rejections", "rejection_reasons"))
    )
    return {
        "kill_switch": kill_switch,
        "daily_pnl_pct": daily_pnl_pct,
        "exposure": exposure,
        "trades_today": trades_today,
        "cooldown_active": cooldown_active,
        "last_rejection_reasons": reasons,
    }


class RiskStateRequestHandler(BaseHTTPRequestHandler):
    """Serve one bound, read-only risk-state snapshot."""

    state: ClassVar[Mapping[str, object]] = {}
    state_provider: ClassVar[object] = None
    risk_config: ClassVar[RiskConfig] = RiskConfig()

    def do_GET(self) -> None:
        """Return risk state for ``GET /api/risk/state`` and 404 otherwise."""
        if urlsplit(self.path).path != RISK_STATE_PATH:
            self._send_json(404, {"error": "not found"})
            return

        provider = self.state_provider
        raw_state = self.state
        if callable(provider):
            raw_state = provider()
        try:
            response = build_risk_state_response(raw_state, risk_config=self.risk_config)
        except (TypeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, response)

    def _send_json(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the read-only panel endpoint quiet unless an app adds logging."""
        return


def make_risk_state_handler(
    state: RiskStateSource | None = None,
    *,
    risk_config: RiskConfig | None = None,
) -> type[RiskStateRequestHandler]:
    """Return a handler class bound to a state source and risk configuration."""
    bound_state = state if state is not None else {}
    bound_config = risk_config or RiskConfig()

    class BoundRiskStateRequestHandler(RiskStateRequestHandler):
        state: ClassVar[Mapping[str, object]] = (
            bound_state if isinstance(bound_state, Mapping) else {}
        )
        state_provider: ClassVar[object] = bound_state if callable(bound_state) else None
        risk_config: ClassVar[RiskConfig] = bound_config

    return BoundRiskStateRequestHandler


def _first(data: Mapping[str, object], names: tuple[str, ...]) -> object:
    for name in names:
        if name in data:
            return data[name]
    return _MISSING


def _read_daily_pnl_pct(data: Mapping[str, object]) -> float:
    direct_value = _first(data, ("daily_pnl_pct", "daily_pnl_percent"))
    if direct_value is not _MISSING:
        return _read_finite_number(direct_value, "daily_pnl_pct")

    pnl_value = _first(data, ("daily_pnl",))
    if pnl_value is _MISSING:
        return 0.0
    daily_pnl = _read_finite_number(pnl_value, "daily_pnl")
    equity_value = _first(data, ("equity",))
    if equity_value is _MISSING:
        raise ValueError("equity is required when daily_pnl is provided")
    equity = _read_finite_number(equity_value, "equity")
    if equity <= 0:
        raise ValueError("equity must be positive")
    return daily_pnl / equity * 100.0


def _read_finite_number(value: object, field: str) -> float:
    if value is _MISSING or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _read_non_negative_number(value: object, field: str, *, default: float) -> float:
    if value is _MISSING:
        return default
    number = _read_finite_number(value, field)
    if number < 0:
        raise ValueError(f"{field} must be non-negative")
    return number


def _read_non_negative_integer(value: object, field: str, *, default: int) -> int:
    if value is _MISSING:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _read_bool(value: object, field: str, *, default: bool | None = None) -> bool:
    if value is _MISSING:
        if default is None:
            raise TypeError(f"{field} must be a boolean")
        return default
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")
    return value


def _read_rejection_reasons(value: object) -> list[str]:
    if value is _MISSING:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, (list, tuple)):
        raise TypeError("last_rejection_reasons must be a list of strings")
    if any(not isinstance(reason, str) for reason in value):
        raise TypeError("last_rejection_reasons must be a list of strings")
    return list(value)


# Explicit aliases for integrations that use verb-oriented endpoint names.
risk_state = build_risk_state_response
get_risk_state = build_risk_state_response
handle_risk_state = build_risk_state_response
