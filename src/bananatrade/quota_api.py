"""Read-only HTTP endpoint for displaying gateway quota usage."""
from __future__ import annotations

import json
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler
from typing import ClassVar, TypedDict, TypeGuard
from urllib.parse import urlsplit

from .gateway.quota import QuotaLedger


class QuotaWindow(TypedDict):
    """Usage and configured limit for one quota window."""

    used: int
    limit: int


class TierQuota(TypedDict):
    """Quota panel data for one configured tier."""

    windows: dict[str, QuotaWindow]
    flagged: bool
    highlighted: bool


class QuotaResponse(TypedDict):
    """JSON shape returned by the quota endpoint."""

    tiers: dict[str, TierQuota]


TierConfig = Mapping[str, object]
TierConfigs = Mapping[str, TierConfig]


class QuotaRequestHandler(BaseHTTPRequestHandler):
    """Serve the quota panel response for a bound ledger and tier config."""

    ledger: ClassVar[QuotaLedger]
    tiers: ClassVar[TierConfigs]

    def do_GET(self) -> None:
        """Return quota usage for ``GET /api/quota`` and 404 otherwise."""
        if urlsplit(self.path).path != "/api/quota":
            self.send_error(404)
            return

        body = json.dumps(
            build_quota_response(self.ledger, self.tiers),
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the read-only panel endpoint quiet unless an app adds logging."""
        return


def make_quota_handler(ledger: QuotaLedger, tiers: TierConfigs) -> type[QuotaRequestHandler]:
    """Bind a quota ledger and tier configuration to an HTTP handler class."""

    bound_ledger = ledger
    bound_tiers = tiers

    class BoundQuotaRequestHandler(QuotaRequestHandler):
        ledger: ClassVar[QuotaLedger] = bound_ledger
        tiers: ClassVar[TierConfigs] = bound_tiers

    return BoundQuotaRequestHandler


def build_quota_response(ledger: QuotaLedger, tiers: TierConfigs) -> QuotaResponse:
    """Build per-tier call usage and limits for the 5-hour and 7-day windows."""
    payload: dict[str, TierQuota] = {}
    for tier, config in tiers.items():
        limit_5h, limit_7d = _quota_limits(config)
        used_5h, used_7d = ledger.counts(tier)
        highlighted = tier == "tier4_cio"
        payload[tier] = {
            "windows": {
                "5h": {"used": used_5h, "limit": limit_5h},
                "7d": {"used": used_7d, "limit": limit_7d},
            },
            "flagged": highlighted,
            "highlighted": highlighted,
        }
    return {"tiers": payload}


def _quota_limits(config: TierConfig) -> tuple[int, int]:
    raw_quota = config.get("quota")
    if not isinstance(raw_quota, Mapping):
        raise TypeError("Each tier must define a quota mapping")

    limit_5h = raw_quota.get("max_calls_per_5h")
    limit_7d = raw_quota.get("max_calls_per_7d")
    if not _is_non_negative_integer(limit_5h) or not _is_non_negative_integer(limit_7d):
        raise ValueError("Quota limits must be non-negative integers")
    return limit_5h, limit_7d


def _is_non_negative_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
