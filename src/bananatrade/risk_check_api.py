"""Paper-trading risk sizing and the ``POST /api/risk/check`` handler.

The endpoint never places an order.  It evaluates a proposed position and returns
an approved decision together with the largest size that satisfies the configured
position cap and the fixed one-percent stop-out budget.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler
from typing import ClassVar, TypedDict
from urllib.parse import urlsplit

from .risk import RiskConfig

MAX_STOP_OUT_PCT = 0.01
RISK_CHECK_PATH = "/api/risk/check"


class RiskCheckResult(TypedDict):
    """JSON response returned by :func:`check_risk`."""

    approved: bool
    reasons: list[str]
    adjusted_size: float


class RiskCheckInputError(ValueError):
    """Raised when a risk-check request is missing or has invalid values."""


def check_risk(
    payload: Mapping[str, object] | None = None,
    *,
    config: RiskConfig | None = None,
    **values: object,
) -> RiskCheckResult:
    """Evaluate a proposed paper position without placing an order.

    ``size`` is a quantity, while ``entry``, ``stop_loss`` and ``take_profit``
    are prices.  The returned size is bounded by both one percent of equity at
    the stop and ``RiskConfig.max_position_pct`` of equity at entry.  Common
    price and size aliases are accepted so the function is usable by dashboard
    clients that use ``*_price`` or ``position_size`` field names.
    """
    data: dict[str, object] = dict(payload or {})
    data.update(values)
    selected_config = config or RiskConfig()

    equity = _read_number(data, ("equity",))
    entry = _read_number(data, ("entry", "entry_price"))
    stop_loss = _read_number(data, ("stop_loss", "stop", "stop_price"))
    take_profit = _read_number(data, ("take_profit", "target", "target_price"))
    requested_size = _read_number(data, ("size", "position_size", "quantity"))

    if equity <= 0:
        raise RiskCheckInputError("equity must be positive")
    if entry <= 0 or stop_loss <= 0 or take_profit <= 0:
        raise RiskCheckInputError("prices must be positive")
    if requested_size <= 0:
        raise RiskCheckInputError("size must be positive")
    if selected_config.max_position_pct <= 0:
        raise RiskCheckInputError("configured maximum position must be positive")

    stop_distance = abs(entry - stop_loss)
    reward_distance = abs(take_profit - entry)
    if stop_distance == 0:
        raise RiskCheckInputError("stop_loss must differ from entry")

    reward_risk = reward_distance / stop_distance
    if reward_risk < selected_config.min_reward_risk:
        return {"approved": False, "reasons": ["minimum reward/risk not met"], "adjusted_size": 0.0}

    stop_risk_size = equity * MAX_STOP_OUT_PCT / stop_distance
    configured_max_size = equity * selected_config.max_position_pct / entry
    adjusted_size = min(requested_size, stop_risk_size, configured_max_size)
    reasons: list[str] = []
    if requested_size > stop_risk_size:
        reasons.append("size adjusted to limit stop-out risk")
    if requested_size > configured_max_size:
        reasons.append("size adjusted to configured maximum")

    return {"approved": True, "reasons": reasons, "adjusted_size": adjusted_size}


def risk_check(
    payload: Mapping[str, object] | None = None,
    *,
    config: RiskConfig | None = None,
    **values: object,
) -> RiskCheckResult:
    """Compatibility alias for :func:`check_risk`."""
    return check_risk(payload, config=config, **values)


def _read_number(data: Mapping[str, object], names: tuple[str, ...]) -> float:
    for name in names:
        if name not in data:
            continue
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RiskCheckInputError(f"{name} must be a finite number")
        number = float(value)
        if not math.isfinite(number):
            raise RiskCheckInputError(f"{name} must be a finite number")
        return number
    raise RiskCheckInputError(f"missing field: {names[0]}")


class RiskCheckRequestHandler(BaseHTTPRequestHandler):
    """Minimal standard-library handler for the risk-check route."""

    risk_config: ClassVar[RiskConfig] = RiskConfig()

    def do_POST(self) -> None:
        """Evaluate JSON requests sent to ``/api/risk/check``."""
        if urlsplit(self.path).path != RISK_CHECK_PATH:
            self._send_json(404, {"error": "not found"})
            return

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(400, {"error": "missing Content-Length"})
            return
        try:
            length = int(content_length)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length"})
            return
        if length < 0:
            self._send_json(400, {"error": "invalid Content-Length"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return
        if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
            self._send_json(400, {"error": "JSON body must be an object"})
            return

        request_data: dict[str, object] = payload
        try:
            result = check_risk(request_data, config=self.risk_config)
        except RiskCheckInputError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, result)

    def _send_json(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_risk_check_handler(config: RiskConfig | None = None) -> type[RiskCheckRequestHandler]:
    """Return a handler class bound to one immutable risk configuration."""
    selected_config = config or RiskConfig()

    class ConfiguredRiskCheckRequestHandler(RiskCheckRequestHandler):
        risk_config: ClassVar[RiskConfig] = selected_config

    return ConfiguredRiskCheckRequestHandler
