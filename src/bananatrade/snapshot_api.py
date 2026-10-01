"""Read-only single-timeframe snapshot payload and HTTP endpoint."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlsplit

import pandas as pd

from .data.snapshot import build_snapshot, closed_candles, is_stale


class SnapshotRequestHandler(BaseHTTPRequestHandler):
    """Serve a bound, read-only ``GET /api/snapshot`` endpoint."""

    candles_by_symbol: ClassVar[Mapping[str, Mapping[str, pd.DataFrame]]]
    as_of: ClassVar[datetime]

    def do_GET(self) -> None:
        """Return one symbol/timeframe snapshot from the bound candle source."""
        parsed = urlsplit(self.path)
        if parsed.path != "/api/snapshot":
            self._send_json(404, {"error": "not found"})
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        symbol = _one_query_value(query, "symbol")
        timeframe = _one_query_value(query, "timeframe")
        if symbol is None or timeframe is None:
            self._send_json(400, {"error": "symbol and timeframe are required"})
            return

        symbol_frames = self.candles_by_symbol.get(symbol)
        if symbol_frames is None or timeframe not in symbol_frames:
            self._send_json(404, {"error": "snapshot data not found"})
            return

        try:
            result = build_snapshot_response(
                symbol=symbol,
                timeframe=timeframe,
                candles=symbol_frames[timeframe],
                as_of=self.as_of,
            )
        except ValueError as exc:
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

    def log_message(self, format: str, *args: object) -> None:
        """Keep the read-only snapshot endpoint quiet."""
        return


def make_snapshot_handler(
    candles_by_symbol: Mapping[str, Mapping[str, pd.DataFrame]],
    *,
    as_of: datetime,
) -> type[SnapshotRequestHandler]:
    """Bind candle data and an observation time to a snapshot handler class."""
    bound_candles = candles_by_symbol
    bound_as_of = as_of

    class BoundSnapshotRequestHandler(SnapshotRequestHandler):
        candles_by_symbol: ClassVar[Mapping[str, Mapping[str, pd.DataFrame]]] = bound_candles
        as_of: ClassVar[datetime] = bound_as_of

    return BoundSnapshotRequestHandler


def _one_query_value(query: Mapping[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if values is None or len(values) != 1 or not values[0].strip():
        return None
    return values[0].strip()


def _as_utc(value: datetime) -> datetime:
    """Return an aware UTC timestamp for consistent API serialization."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime) -> str:
    """Serialize a timestamp using the dashboard's canonical UTC representation."""
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def build_snapshot_response(
    *,
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    as_of: datetime,
) -> dict[str, Any]:
    """Build a JSON-ready snapshot for one symbol and timeframe.

    The existing market snapshot builder remains the single source for the last
    close and indicator values. The requested timeframe is used for freshness,
    rather than the builder's default timeframe.
    """
    normalized_as_of = _as_utc(as_of)
    closed = closed_candles(candles, timeframe, normalized_as_of)
    if closed.empty:
        raise ValueError(f"No closed candles for {symbol} at {timeframe}")

    snapshot = build_snapshot(
        symbol,
        {timeframe: candles},
        orderbook=None,
        funding=None,
        as_of=normalized_as_of,
    )
    summary = snapshot.timeframes[timeframe]
    timestamp = _isoformat(normalized_as_of)
    candle_records = [
        {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        for _, row in closed.iterrows()
    ]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "last_price": summary.last_price,
        "candles": candle_records,
        "indicators": dict(summary.indicators),
        "timestamp": timestamp,
        "as_of": timestamp,
        "stale": is_stale(closed, timeframe, normalized_as_of),
    }
