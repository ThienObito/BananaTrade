"""Optional MetaTrader 5 terminal data adapter.

Credentials are intentionally absent. ``connect`` attaches only to terminal
already opened and authenticated by owner.
"""

from __future__ import annotations

import csv
import importlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any


class MT5Unavailable(RuntimeError):
    """Raised when official MetaTrader5 package is unavailable."""


class MT5ConnectionError(RuntimeError):
    """Raised when terminal initialization fails."""


@dataclass(frozen=True)
class MT5SymbolSpec:
    """Fields needed by brain and executor."""

    name: str
    digits: int
    point: float
    volume_min: float
    volume_step: float
    volume_max: float
    stops_level: int
    filling_mode: int
    spread: float


class MT5Client:
    """Small, mockable wrapper around official ``MetaTrader5`` module."""

    def __init__(self, mt5_module: ModuleType | None = None, cache_dir: str | Path = "data/history") -> None:
        self.mt5 = mt5_module
        self.cache_dir = Path(cache_dir)
        self.connected = False
        self.resolved_symbols: dict[str, str] = {}

    def _module(self) -> ModuleType:
        if self.mt5 is None:
            try:
                self.mt5 = importlib.import_module("MetaTrader5")
            except ImportError as exc:
                raise MT5Unavailable("MetaTrader5 package is not installed") from exc
        return self.mt5

    def connect(self) -> bool:
        """Attach to currently logged-in terminal; never supply credentials."""
        module = self._module()
        result = module.initialize()
        if not result:
            raise MT5ConnectionError(str(module.last_error()))
        self.connected = True
        return True

    def shutdown(self) -> None:
        if self.mt5 is not None and self.connected:
            self.mt5.shutdown()
        self.connected = False

    def resolve_symbol(self, requested: str) -> str:
        cached = self.resolved_symbols.get(requested)
        if cached is not None:
            return cached
        module = self._module()
        symbols = module.symbols_get()
        if symbols is None:
            raise MT5ConnectionError("symbols_get returned no symbols")
        normalized = requested.upper().replace("/", "")
        exact = [item for item in symbols if str(getattr(item, "name", "")).upper() == normalized]
        candidates = exact or [item for item in symbols if str(getattr(item, "name", "")).upper().startswith(normalized)]
        if not candidates:
            raise KeyError(f"MT5 symbol not found: {requested}")
        name = str(candidates[0].name)
        self.resolved_symbols[requested] = name
        module.symbol_select(name, True)
        return name

    def timeframe_value(self, label: str) -> int:
        """Resolve canonical label to official MT5 timeframe constant."""
        name = {"M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1"}.get(label)
        if name is None:
            raise ValueError(f"unsupported MT5 timeframe: {label}")
        value = getattr(self._module(), name, None)
        if not isinstance(value, int):
            raise MT5ConnectionError(f"MT5 module missing {name}")
        return value

    def get_rates_range(self, symbol: str, timeframe: int, start: datetime, end: datetime) -> list[dict[str, object]]:
        """Fetch bars for UTC date range using official MT5 API."""
        module = self._module()
        resolved = self.resolve_symbol(symbol)
        start_utc = start.astimezone(UTC) if start.tzinfo is not None else start.replace(tzinfo=UTC)
        end_utc = end.astimezone(UTC) if end.tzinfo is not None else end.replace(tzinfo=UTC)
        rates = module.copy_rates_range(resolved, timeframe, start_utc, end_utc)
        if rates is None:
            raise MT5ConnectionError(str(module.last_error()))
        rows = [_rate_row(row) for row in rates]
        self._write_cache(resolved, timeframe, rows)
        return rows

    def get_rates(self, symbol: str, timeframe: int, count: int = 500) -> list[dict[str, object]]:
        module = self._module()
        resolved = self.resolve_symbol(symbol)
        rates = module.copy_rates_from_pos(resolved, timeframe, 0, count)
        if rates is None:
            raise MT5ConnectionError(str(module.last_error()))
        rows = [_rate_row(row) for row in rates]
        self._write_cache(resolved, timeframe, rows)
        return rows

    def closed_rates(self, symbol: str, timeframe: int, count: int = 500) -> list[dict[str, object]]:
        """Return rates excluding still-forming latest bar."""
        rows = self.get_rates(symbol, timeframe, count + 1)
        return rows[:-1] if len(rows) > 1 else []

    def get_tick(self, symbol: str) -> dict[str, float]:
        module = self._module()
        resolved = self.resolve_symbol(symbol)
        tick = module.symbol_info_tick(resolved)
        if tick is None:
            raise MT5ConnectionError(str(module.last_error()))
        return {
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "last": float(getattr(tick, "last", 0.0)),
            "time": float(getattr(tick, "time", 0.0)),
        }

    def symbol_spec(self, symbol: str) -> MT5SymbolSpec:
        module = self._module()
        resolved = self.resolve_symbol(symbol)
        info = module.symbol_info(resolved)
        if info is None:
            raise MT5ConnectionError(str(module.last_error()))
        tick = self.get_tick(resolved)
        return MT5SymbolSpec(
            resolved,
            int(info.digits),
            float(info.point),
            float(info.volume_min),
            float(info.volume_step),
            float(info.volume_max),
            int(info.trade_stops_level),
            int(info.filling_mode),
            float(tick["ask"] - tick["bid"]),
        )

    def _write_cache(self, symbol: str, timeframe: int, rows: list[dict[str, object]]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"mt5_{symbol}_{_timeframe_name(timeframe)}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            fields = ("timestamp", "datetime", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def _timeframe_name(timeframe: int) -> str:
    """Map common MT5 constants to canonical research cache names."""
    names = {
        1: "M1",
        5: "M5",
        15: "M15",
        30: "M30",
        60: "H1",
        240: "H4",
        1440: "D1",
        16385: "H1",
    }
    return names.get(timeframe, str(timeframe))


def _rate_row(row: Any) -> dict[str, object]:
    timestamp = int(row["time"] if isinstance(row, dict) else row.time)
    values: dict[str, object] = {}
    for name in ("open", "high", "low", "close", "tick_volume", "spread", "real_volume"):
        values[name] = float(row[name] if isinstance(row, dict) else getattr(row, name))
    values["timestamp"] = timestamp
    values["datetime"] = datetime.fromtimestamp(timestamp, UTC).isoformat()
    return values
