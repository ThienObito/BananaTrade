"""BananaTrade runtime configuration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Serializable paper-trading application configuration."""

    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    initial_equity: float = 10_000.0
    risk_pct: float = 0.01
    max_positions: int = 3
    entry_hypothesis: str = "H1"
    exit_model: str = "fixed_2r"
    ws_url: str = "ws://localhost:8765"
    server_host: str = "localhost"
    server_port: int = 8000
    mt5_execution_enabled: bool = False
    mt5_volume_max: float | None = None
    mt5_magic: int = 59040
    mt5_timeframe: int = 15
    commission_per_lot: float = 0.0
    strategy_candidate: str | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.commission_per_lot) or self.commission_per_lot < 0:
            raise ValueError("commission_per_lot must be non-negative and finite")

    @classmethod
    def load_from_file(cls, path: str | Path) -> Config:
        """Load configuration from a JSON object."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("config JSON must be an object")
        fields = {
            "symbol",
            "timeframe",
            "initial_equity",
            "risk_pct",
            "max_positions",
            "entry_hypothesis",
            "exit_model",
            "mt5_execution_enabled",
            "mt5_volume_max",
            "mt5_magic",
            "mt5_timeframe",
            "commission_per_lot",
            "strategy_candidate",
            "ws_url",
            "server_host",
            "server_port",
        }
        if not fields.issuperset(data):
            raise ValueError("config JSON contains unknown fields")
        return cls(**{key: value for key, value in data.items() if key in fields})

    def save_to_file(self, path: str | Path) -> None:
        """Write configuration as readable JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load_from_env(cls) -> Config:
        """Load supported overrides from ``BT_*`` environment variables."""
        return cls(
            symbol=os.getenv("BT_SYMBOL", cls.symbol),
            timeframe=os.getenv("BT_TIMEFRAME", cls.timeframe),
            initial_equity=_env_float("BT_EQUITY", cls.initial_equity),
            risk_pct=_env_float("BT_RISK_PCT", cls.risk_pct),
            max_positions=_env_int("BT_MAX_POSITIONS", cls.max_positions),
            entry_hypothesis=os.getenv("BT_ENTRY_HYPOTHESIS", cls.entry_hypothesis),
            exit_model=os.getenv("BT_EXIT_MODEL", cls.exit_model),
            mt5_execution_enabled=_env_bool("BT_MT5_EXECUTION_ENABLED", cls.mt5_execution_enabled),
            mt5_volume_max=_env_optional_float("BT_MT5_VOLUME_MAX", cls.mt5_volume_max),
            mt5_magic=_env_int("BT_MT5_MAGIC", cls.mt5_magic),
            mt5_timeframe=_env_int("BT_MT5_TIMEFRAME", cls.mt5_timeframe),
            commission_per_lot=_env_float("BT_COMMISSION_PER_LOT", cls.commission_per_lot),
            strategy_candidate=os.getenv("BT_STRATEGY_CANDIDATE", cls.strategy_candidate),
        )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _env_optional_float(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
