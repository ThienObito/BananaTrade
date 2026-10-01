"""Read-only latest-signal payload and HTTP endpoint."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from typing import ClassVar, Literal, TypedDict
from urllib.parse import parse_qs, urlsplit

import pandas as pd

from .data.snapshot import closed_candles, is_stale

SignalBias = Literal["LONG", "SHORT", "NEUTRAL"]


class SignalResponse(TypedDict):
    """JSON shape returned by the latest-signal endpoint."""

    symbol: str
    bias: SignalBias
    confidence: float
    as_of: str
    stale: bool


class SignalRequestHandler(BaseHTTPRequestHandler):
    """Serve one bound latest signal for a symbol and timeframe."""

    candles_by_symbol: ClassVar[Mapping[str, Mapping[str, pd.DataFrame]]]
    as_of: ClassVar[datetime]
    bias: ClassVar[str]
    confidence: ClassVar[float]

    def do_GET(self) -> None:
        """Return a validated signal payload for ``GET /api/signal``."""
        parsed = urlsplit(self.path)
        if parsed.path != "/api/signal":
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
            self._send_json(404, {"error": "signal data not found"})
            return

        try:
            result = build_signal_response(
                symbol=symbol,
                timeframe=timeframe,
                candles=symbol_frames[timeframe],
                as_of=self.as_of,
                bias=self.bias,
                confidence=self.confidence,
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
        """Keep the read-only signal endpoint quiet."""
        return


def make_signal_handler(
    candles_by_symbol: Mapping[str, Mapping[str, pd.DataFrame]],
    *,
    as_of: datetime,
    bias: str = "NEUTRAL",
    confidence: float = 0.5,
) -> type[SignalRequestHandler]:
    """Bind candle data and signal values to an HTTP handler class."""
    bound_candles = candles_by_symbol
    bound_as_of = as_of
    bound_bias = bias
    bound_confidence = confidence

    class BoundSignalRequestHandler(SignalRequestHandler):
        candles_by_symbol: ClassVar[Mapping[str, Mapping[str, pd.DataFrame]]] = bound_candles
        as_of: ClassVar[datetime] = bound_as_of
        bias: ClassVar[str] = bound_bias
        confidence: ClassVar[float] = bound_confidence

    return BoundSignalRequestHandler


def build_signal_response(
    *,
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    as_of: datetime,
    bias: str,
    confidence: float,
) -> SignalResponse:
    """Build a latest-signal response with three-bar freshness semantics."""
    normalized_bias = _normalise_bias(bias)
    normalized_confidence = _normalise_confidence(confidence)
    normalized_as_of = _as_utc(as_of)
    closed = closed_candles(candles, timeframe, normalized_as_of)
    if closed.empty:
        raise ValueError(f"No closed candles for {symbol} at {timeframe}")
    return {
        "symbol": symbol,
        "bias": normalized_bias,
        "confidence": normalized_confidence,
        "as_of": _isoformat(normalized_as_of),
        "stale": is_stale(closed, timeframe, normalized_as_of, max_age_bars=3),
    }


def _normalise_bias(value: str) -> SignalBias:
    normalized = value.strip().upper()
    if normalized == "LONG":
        return "LONG"
    if normalized == "SHORT":
        return "SHORT"
    if normalized == "NEUTRAL":
        return "NEUTRAL"
    raise ValueError("bias must be LONG, SHORT, or NEUTRAL")


def _normalise_confidence(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("confidence must be a finite number")
    if value < 0 or value > 1:
        raise ValueError("confidence must be between 0 and 1")
    return float(value)


def _one_query_value(query: Mapping[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if values is None or len(values) != 1 or not values[0].strip():
        return None
    return values[0].strip()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


__all__ = [
    "SignalRequestHandler",
    "SignalResponse",
    "build_signal_response",
    "make_signal_handler",
]
