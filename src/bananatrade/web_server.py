"""Local dashboard server with a read-only live Kraken market endpoint."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from math import isfinite
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

from .agents.execution.auto_trader import AutoTrader
from .analytics.performance import compute_metrics
from .backtest.engine import BacktestEngine
from .backtest.report import generate_report
from .backtest.walk_forward import WalkForwardOptimizer
from .brokers.mt5_executor import MT5Executor
from .config import Config
from .engine.adaptive_trader import AdaptiveTrader
from .engine.regime_detector import RegimeDetector
from .engine.strategy import MACrossStrategy
from .feeds.feed_manager import FeedManager
from .paper_broker import Fill, PaperBroker
from .risk import RiskEngine
from .risk_manager import RiskManager
from .runtime import RuntimeService
from .signal_api import SignalResponse, build_signal_response
from .snapshot_api import build_snapshot_response
from .storage.db import initialize
from .ws_broadcaster import StdlibWebSocket, WsBroadcaster

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "bananatrade.db"
SNAPSHOT_SYMBOL = "BTC/USDT"
SNAPSHOT_TIMEFRAME = "1h"
SNAPSHOT_CANDLES = ROOT / "tests" / "fixtures" / "synthetic_btc_usdt_1h.csv"
VALID_BIASES = frozenset({"LONG", "SHORT", "NEUTRAL"})
initialize(DB_PATH)
BROKER = PaperBroker(10000.0, RiskEngine(), fee_rate=0.0004)
BROADCASTER = WsBroadcaster()
RISK_MANAGER = RiskManager()
REGIME_DETECTOR = RegimeDetector()
ADAPTIVE_TRADER = AdaptiveTrader(AutoTrader(BROKER), risk_manager=RISK_MANAGER, regime_detector=REGIME_DETECTOR)
FEED_MANAGER = FeedManager(Config(symbol="BTCUSDT"), broadcaster=BROADCASTER)
MT5_EXECUTOR = MT5Executor(Config())
LOGGER = logging.getLogger(__name__)
SERVER_STARTED_AT = datetime.now(UTC)
JOURNAL_PATH = ROOT / "trades" / "journal.csv"
_INTERNAL_ERROR_BODY = b'{"error":"Internal server error"}'


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server that converts uncaught handler failures to JSON."""

    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Log an uncaught request failure and return a safe JSON response."""
        LOGGER.exception("unexpected HTTP request failure from %s", client_address)
        response = (
            b"HTTP/1.1 500 Internal Server Error\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: "
            + str(len(_INTERNAL_ERROR_BODY)).encode("ascii")
            + b"\r\nConnection: close\r\n\r\n"
            + _INTERNAL_ERROR_BODY
        )
        try:
            request.sendall(response)
        except OSError:
            LOGGER.exception("failed to send unexpected HTTP error response")


def ensure_fill_table() -> None:
    """Create the paper-fill table when it is not already present."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS paper_fills "
            "(order_id TEXT PRIMARY KEY, symbol TEXT, side TEXT, quantity REAL, "
            "price REAL, fee REAL, created_at TEXT)"
        )


def restore_broker() -> None:
    """Restore persisted paper fills into the in-memory broker."""
    ensure_fill_table()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT symbol, side, quantity, price FROM paper_fills ORDER BY rowid"
        ).fetchall()
    for symbol, side, quantity, price in rows:
        BROKER.submit_market(symbol, side, quantity, price)


def record_fill(fill: Fill) -> None:
    """Persist one paper fill without exposing database details to clients."""
    with sqlite3.connect(DB_PATH) as db:
        ensure_fill_table()
        db.execute(
            "INSERT OR REPLACE INTO paper_fills "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (fill.order_id, fill.symbol, fill.side, fill.quantity, fill.price, fill.fee),
        )


def broker_state() -> dict[str, Any]:
    """Return current paper-broker state with stable dashboard fields."""
    state = BROKER.state()
    return {
        "cash": state["cash"],
        "positions": state["positions"],
        "open_orders": state["open_orders"],
    }


def risk_state() -> dict[str, object]:
    """Return dashboard risk metrics derived from the paper broker."""
    state = BROKER.state()
    equity_value = state["equity"]
    if not isinstance(equity_value, (int, float)) or isinstance(equity_value, bool):
        return {"open_positions": 0, "daily_pnl": 0.0, "daily_pnl_pct": 0.0, "peak_equity": 0.0, "current_equity": 0.0, "drawdown_pct": 0.0, "trading_halted": True}
    current_equity = float(equity_value)
    peak_equity = max(BROKER.initial_cash, current_equity)
    daily_pnl = current_equity - BROKER.initial_cash
    positions = state.get("positions", [])
    open_positions = len(positions) if isinstance(positions, list) else 0
    daily_pnl_pct = daily_pnl / BROKER.initial_cash if BROKER.initial_cash else 0.0
    drawdown_pct = (peak_equity - current_equity) / peak_equity if peak_equity else 0.0
    return {
        "open_positions": open_positions,
        "daily_pnl": daily_pnl,
        "daily_pnl_pct": daily_pnl_pct,
        "peak_equity": peak_equity,
        "current_equity": current_equity,
        "drawdown_pct": drawdown_pct,
        "trading_halted": RISK_MANAGER.check_drawdown(current_equity, peak_equity),
    }


def walkforward_state() -> dict[str, object]:
    """Run default walk-forward optimization on dashboard candles."""
    candles = _snapshot_frame().tail(500).to_dict("records")
    result = WalkForwardOptimizer().optimize(
        candles,
        MACrossStrategy,
        {"ma_fast": [10, 20], "ma_slow": [40, 50]},
    )
    return {
        "windows": [
            {
                "train_start": window.train_start,
                "train_end": window.train_end,
                "test_start": window.test_start,
                "test_end": window.test_end,
                "best_params": window.best_params,
                "train_sharpe": window.train_sharpe,
                "test_sharpe": window.test_sharpe,
            }
            for window in result.windows
        ],
        "avg_sharpe": result.avg_sharpe,
        "stability_score": result.stability_score,
    }


def performance_state() -> dict[str, object]:
    """Return performance metrics from the paper-trade CSV journal."""
    if not JOURNAL_PATH.exists():
        return compute_metrics([]).as_dict()
    with JOURNAL_PATH.open("r", newline="", encoding="utf-8") as handle:
        import csv

        return compute_metrics(csv.DictReader(handle)).as_dict()


def health_state() -> dict[str, object]:
    """Return feed and process health for dashboard monitoring."""
    now = datetime.now(UTC)
    uptime = max(0.0, (now - SERVER_STARTED_AT).total_seconds())
    last_candle = FEED_MANAGER.last_candle_at
    return {
        "status": "ok" if FEED_MANAGER.connected else "degraded",
        "feed_connected": FEED_MANAGER.connected,
        "last_candle_at": datetime.fromtimestamp(last_candle, UTC).isoformat() if last_candle is not None else None,
        "uptime_seconds": uptime,
    }


def mt5_status() -> dict[str, object]:
    """Return MT5 terminal and demo-execution status."""
    status = MT5_EXECUTOR.status()
    return {
        "connected": status.get("connected", False),
        "account_mode": status.get("account_mode", "UNKNOWN"),
        "execution_enabled": status.get("execution_enabled", False),
        "last_decision": status.get("last_decision"),
        "open_positions": status.get("open_positions", 0),
        "today_pnl": status.get("today_pnl", 0.0),
    }


def adaptive_status() -> dict[str, object]:
    """Return adaptive trader controls for dashboard clients."""
    return ADAPTIVE_TRADER.status()


def regime_state() -> dict[str, object]:
    """Return latest detector values, computing them from dashboard candles."""
    candles = _snapshot_frame().to_dict("records")
    REGIME_DETECTOR.detect(candles)
    snapshot = REGIME_DETECTOR.last_snapshot
    if snapshot is None:
        return {"regime": "RANGING", "adx": 0.0, "atr_pct": 0.0, "confidence": 0.0}
    return {
        "regime": snapshot.regime.value,
        "adx": snapshot.adx,
        "atr_pct": snapshot.atr_pct,
        "confidence": snapshot.confidence,
    }


def _send_json(
    handler: SimpleHTTPRequestHandler,
    status: int,
    payload: Mapping[str, object],
) -> None:
    """Send a compact JSON response with a stable content type."""
    body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _as_float(value: object, field: str) -> float:
    """Convert a finite positive JSON number or raise a client-input error."""
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        raise TypeError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return result


def _snapshot_frame() -> pd.DataFrame:
    """Load committed offline candles used by local paper dashboard APIs."""
    return pd.read_csv(SNAPSHOT_CANDLES)


def _snapshot_as_of(candles: pd.DataFrame) -> datetime:
    last_open = int(candles.iloc[-1]["timestamp_ms"])
    return datetime.fromtimestamp((last_open + 3_600_000) / 1000, UTC)


def _snapshot_payload() -> dict[str, object]:
    """Build dashboard snapshot from committed offline candles only."""
    candles = _snapshot_frame()
    return build_snapshot_response(
        symbol=SNAPSHOT_SYMBOL,
        timeframe=SNAPSHOT_TIMEFRAME,
        candles=candles,
        as_of=_snapshot_as_of(candles),
    )


def _signal_payload() -> SignalResponse:
    """Build latest paper signal from the same committed candle source."""
    candles = _snapshot_frame()
    return build_signal_response(
        symbol=SNAPSHOT_SYMBOL,
        timeframe=SNAPSHOT_TIMEFRAME,
        candles=candles,
        as_of=_snapshot_as_of(candles),
        bias="LONG",
        confidence=0.75,
    )


restore_broker()


class Handler(SimpleHTTPRequestHandler):
    """HTTP request handler for paper-trading and analysis endpoints."""

    websocket_route = "/ws"

    def websocket_client(self) -> object | None:
        """Return a WebSocket adapter when an ASGI server supplies one."""
        return None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def _read_json_body(self) -> dict[str, object]:
        """Read and validate a JSON object from the request body."""
        content_length = int(self.headers.get("Content-Length", "0"))
        parsed = json.loads(self.rfile.read(content_length))
        if not isinstance(parsed, dict):
            raise TypeError("request body must be a JSON object")
        return parsed

    def do_POST(self) -> None:
        """Handle paper-order and backtest requests."""
        path = urlparse(self.path).path
        if path == "/api/backtest":
            try:
                self._run_backtest()
            except (ValueError, KeyError, TypeError) as exc:
                _send_json(self, 400, {"error": str(exc)})
            return
        if path != "/api/paper/order":
            self.send_error(404)
            return

        try:
            data = self._read_json_body()
            symbol = data["symbol"]
            side = data["side"]
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("symbol must be a non-empty string")
            if not isinstance(side, str) or side.upper() not in {"BUY", "SELL"}:
                raise ValueError("side must be BUY or SELL")
            quantity = _as_float(data["qty"], "qty")
            price = _as_float(data["price"], "price")
            fill = BROKER.submit_market(
                symbol,
                side,
                quantity,
                price,
                trades_today=0,
                consecutive_losses=0,
            )
            record_fill(fill)
            _send_json(
                self,
                200,
                {"order": vars(fill), "paper": True, "risk_gated": True},
            )
        except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            _send_json(self, 400, {"error": str(exc)})

    def _run_backtest(self) -> None:
        data = self._read_json_body()
        raw_candles = data.get("candles")
        if not isinstance(raw_candles, list) or not all(isinstance(item, dict) for item in raw_candles):
            raise ValueError("candles must be a list of objects")
        initial_equity = data.get("initial_equity", 10_000.0)
        if not isinstance(initial_equity, (int, float)) or isinstance(initial_equity, bool):
            return _send_json(self, 400, {"error": "initial_equity must be numeric"})
        result = BacktestEngine().run(raw_candles, MACrossStrategy(), float(initial_equity))
        _send_json(self, 200, {**generate_report(result), "trades": result.trades, "equity_curve": result.equity_curve})

    def _send_websocket_route_response(self) -> None:
        """Upgrade browser clients to a minimal server-side WebSocket stream."""
        if self.headers.get("Upgrade", "").lower() != "websocket":
            _send_json(self, 426, {"error": "WebSocket upgrade required", "path": self.websocket_route})
            return
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            _send_json(self, 400, {"error": "missing Sec-WebSocket-Key"})
            return
        import base64
        import hashlib

        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        client = StdlibWebSocket(self.wfile)
        asyncio.run(BROADCASTER.register(client))
        try:
            client.send_json({"symbol": SNAPSHOT_SYMBOL, "price": _snapshot_payload()["last_price"], "timestamp": datetime.now(UTC).timestamp()})
            while True:
                if not self.rfile.read(2):
                    break
        except (OSError, ConnectionError):
            pass
        finally:
            asyncio.run(BROADCASTER.unregister(client))

    def do_GET(self) -> None:
        """Handle API reads and protect clients from unexpected failures."""
        parsed = urlparse(self.path)
        if parsed.path == self.websocket_route:
            self._send_websocket_route_response()
            return
        if parsed.path == "/api/health":
            _send_json(self, 200, health_state())
            return
        if parsed.path == "/api/performance":
            _send_json(self, 200, performance_state())
            return
        if parsed.path == "/api/candles":
            query = parse_qs(parsed.query, keep_blank_values=True)
            symbol = query.get("symbol", [None])[0]
            timeframe = query.get("timeframe", [None])[0]
            if symbol != SNAPSHOT_SYMBOL or timeframe != SNAPSHOT_TIMEFRAME:
                _send_json(self, 404, {"error": "candle data not found"})
                return
            snapshot = _snapshot_payload()
            _send_json(
                self,
                200,
                {
                    "symbol": SNAPSHOT_SYMBOL,
                    "timeframe": SNAPSHOT_TIMEFRAME,
                    "candles": snapshot.get("candles", []),
                },
            )
            return
        if parsed.path == "/api/signal":
            query = parse_qs(parsed.query, keep_blank_values=True)
            symbol = query.get("symbol", [None])[0]
            timeframe = query.get("timeframe", [None])[0]
            if symbol != SNAPSHOT_SYMBOL or timeframe != SNAPSHOT_TIMEFRAME:
                _send_json(self, 404, {"error": "signal data not found"})
                return
            _send_json(self, 200, _signal_payload())
            return
        if parsed.path == "/api/snapshot":
            query = parse_qs(parsed.query, keep_blank_values=True)
            symbol = query.get("symbol", [None])[0]
            timeframe = query.get("timeframe", [None])[0]
            if symbol != SNAPSHOT_SYMBOL or timeframe != SNAPSHOT_TIMEFRAME:
                _send_json(self, 404, {"error": "snapshot data not found"})
                return
            _send_json(self, 200, _snapshot_payload())
            return
        if parsed.path == "/api/paper/state":
            _send_json(self, 200, broker_state())
            return
        if parsed.path == "/api/risk":
            _send_json(self, 200, risk_state())
            return
        if parsed.path == "/api/regime":
            _send_json(self, 200, regime_state())
            return
        if parsed.path == "/api/adaptive_status":
            _send_json(self, 200, adaptive_status())
            return
        if parsed.path == "/api/mt5_status":
            _send_json(self, 200, mt5_status())
            return
        if parsed.path == "/api/walkforward":
            _send_json(self, 200, walkforward_state())
            return
        if parsed.path == "/api/analysis/run":
            try:
                result = asyncio.run(
                    RuntimeService(ROOT, ROOT / "data" / "bananatrade.db").run("BTC/USDT")
                )
                reports = result.get("reports", [])
                if isinstance(reports, list):
                    for report in reports:
                        if isinstance(report, dict) and report.get("bias") not in VALID_BIASES:
                            report["bias"] = "NEUTRAL"
                _send_json(self, 200, result)
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                _send_json(self, 503, {"error": str(exc)})
            return
        super().do_GET()


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the local dashboard until the process is stopped."""
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve(os.getenv("BANANATRADE_HOST", "127.0.0.1"), int(os.getenv("BANANATRADE_PORT", "8765")))
