"""Demo-only MetaTrader 5 execution adapter with hard safety gates."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from math import floor, isfinite
from types import ModuleType
from typing import Any

from ..brain import Decision
from ..config import Config
from .mt5_client import MT5SymbolSpec


class LiveAccountRefused(RuntimeError):
    """Raised whenever terminal account is not a demo account."""


class MT5OrderRefused(RuntimeError):
    """Raised when mandatory order safety checks fail."""


@dataclass(frozen=True)
class ExecutionResult:
    sent: bool
    dry_run: bool
    order_id: str | None
    message: str


class MT5Executor:
    """Send only demo orders, with dry-run default and deterministic guards."""

    def __init__(self, config: Config | None = None, mt5_module: ModuleType | None = None) -> None:
        self.config = config or Config()
        self.mt5 = mt5_module
        self.disabled = False
        self.last_message = "not connected"
        self.last_decision: Decision | None = None

    def _module(self) -> ModuleType:
        if self.mt5 is None:
            try:
                self.mt5 = importlib.import_module("MetaTrader5")
            except ImportError as exc:
                raise MT5OrderRefused("MetaTrader5 package is not installed") from exc
        return self.mt5

    def _require_demo(self) -> Any:
        if self.disabled:
            raise LiveAccountRefused("MT5 execution disabled after account safety refusal")
        module = self._module()
        account = module.account_info()
        demo_mode = getattr(module, "ACCOUNT_TRADE_MODE_DEMO", 0)
        if account is None or getattr(account, "trade_mode", None) != demo_mode:
            self.disabled = True
            raise LiveAccountRefused("non-demo MT5 account refused")
        return account

    def status(self) -> dict[str, object]:
        try:
            account = self._require_demo()
            return {
                "connected": True,
                "account_mode": "DEMO",
                "execution_enabled": self.config.mt5_execution_enabled and not self.disabled,
                "last_decision": self.last_decision.as_dict() if self.last_decision else None,
                "open_positions": self._positions_count(),
                "today_pnl": float(getattr(account, "profit", 0.0)),
            }
        except (LiveAccountRefused, MT5OrderRefused, AttributeError):
            return {
                "connected": False,
                "account_mode": "REFUSED" if self.disabled else "UNKNOWN",
                "execution_enabled": False,
                "last_decision": self.last_decision.as_dict() if self.last_decision else None,
                "open_positions": 0,
                "today_pnl": 0.0,
            }

    def execute(self, symbol: str, decision: Decision, spec: MT5SymbolSpec, *, today_pnl: float = 0.0) -> ExecutionResult:
        self.last_decision = decision
        self._require_demo()
        if decision.side == "NONE":
            return ExecutionResult(False, True, None, "NONE decision; no order")
        if decision.sl is None or decision.tp is None or decision.entry is None:
            raise MT5OrderRefused("SL and TP are required")
        if self._daily_loss_exceeded(today_pnl):
            raise MT5OrderRefused("daily loss kill switch active")
        if self._positions_count(symbol) >= 1:
            raise MT5OrderRefused("maximum one position per symbol")
        volume = self._round_volume(decision.volume, spec)
        if volume < spec.volume_min:
            raise MT5OrderRefused("volume below symbol minimum")
        self._validate_stops(decision, spec)
        request = self._request(symbol, decision, spec, volume)
        if not self.config.mt5_execution_enabled:
            self.last_message = "dry-run; order_send not called"
            return ExecutionResult(False, True, None, self.last_message)
        module = self._module()
        check = module.order_check(request)
        if check is None or not self._retcode_ok(getattr(check, "retcode", None)):
            raise MT5OrderRefused(f"order_check rejected: {getattr(check, 'comment', check)}")
        result = module.order_send(request)
        if result is None or not self._retcode_ok(getattr(result, "retcode", None)):
            raise MT5OrderRefused(f"order_send rejected: {getattr(result, 'comment', result)}")
        order_id = str(getattr(result, "order", getattr(result, "deal", "")))
        self.last_message = "order sent"
        return ExecutionResult(True, False, order_id, self.last_message)

    def close_all_positions(self, magic: int | None = None) -> list[ExecutionResult]:
        self._require_demo()
        module = self._module()
        results: list[ExecutionResult] = []
        for position in module.positions_get() or ():
            if magic is not None and int(getattr(position, "magic", -1)) != magic:
                continue
            results.append(self._close_one(position))
        return results

    def _close_one(self, position: Any) -> ExecutionResult:
        self._require_demo()
        module = self._module()
        request = {"action": getattr(module, "TRADE_ACTION_DEAL", 1), "position": int(position.ticket), "symbol": str(position.symbol), "volume": float(position.volume), "magic": self.config.mt5_magic, "comment": "BananaTrade-DEMO"}
        if not self.config.mt5_execution_enabled:
            return ExecutionResult(False, True, None, "dry-run close; order_send not called")
        check = module.order_check(request)
        if check is None or not self._retcode_ok(getattr(check, "retcode", None)):
            raise MT5OrderRefused("close order_check rejected")
        result = module.order_send(request)
        if result is None or not self._retcode_ok(getattr(result, "retcode", None)):
            raise MT5OrderRefused("close order_send rejected")
        return ExecutionResult(True, False, str(getattr(result, "order", "")), "position closed")

    def _request(self, symbol: str, decision: Decision, spec: MT5SymbolSpec, volume: float) -> dict[str, object]:
        module = self._module()
        side = module.ORDER_TYPE_BUY if decision.side == "BUY" else module.ORDER_TYPE_SELL
        return {"action": module.TRADE_ACTION_DEAL, "symbol": symbol, "volume": volume, "type": side, "price": decision.entry, "sl": decision.sl, "tp": decision.tp, "deviation": 20, "magic": self.config.mt5_magic, "comment": "BananaTrade-DEMO", "type_time": getattr(module, "ORDER_TIME_GTC", 0), "type_filling": self._filling(module, spec.filling_mode)}

    def _filling(self, module: ModuleType, filling_mode: int) -> int:
        for candidate in (getattr(module, "ORDER_FILLING_FOK", 0), getattr(module, "ORDER_FILLING_IOC", 1), getattr(module, "ORDER_FILLING_RETURN", 2)):
            if filling_mode & (1 << candidate) or filling_mode == candidate:
                return candidate
        return getattr(module, "ORDER_FILLING_RETURN", 2)

    def _validate_stops(self, decision: Decision, spec: MT5SymbolSpec) -> None:
        minimum = spec.stops_level * spec.point
        if decision.entry is None or decision.sl is None or decision.tp is None:
            raise MT5OrderRefused("SL and TP are required")
        if abs(decision.entry - decision.sl) < minimum or abs(decision.tp - decision.entry) < minimum:
            raise MT5OrderRefused("SL/TP violate stops_level")

    def _round_volume(self, volume: float, spec: MT5SymbolSpec) -> float:
        if not isfinite(volume) or volume <= 0:
            return 0.0
        configured_cap = spec.volume_min if self.config.mt5_volume_max is None else self.config.mt5_volume_max
        capped = min(volume, spec.volume_max, configured_cap)
        steps = floor(capped / spec.volume_step)
        return round(steps * spec.volume_step, 8)

    def _daily_loss_exceeded(self, today_pnl: float) -> bool:
        account = self._module().account_info()
        equity = float(getattr(account, "equity", 0.0))
        if not equity > 0:
            # Fail closed: without equity the 3% daily-loss kill switch cannot be evaluated.
            raise MT5OrderRefused("account equity unavailable; daily loss kill switch cannot be evaluated")
        return today_pnl / equity <= -0.03

    def _positions_count(self, symbol: str | None = None) -> int:
        positions = self._module().positions_get() or ()
        return sum(1 for position in positions if symbol is None or str(getattr(position, "symbol", "")) == symbol)

    @staticmethod
    def _retcode_ok(retcode: object) -> bool:
        return retcode in {10008, 10009, 10010, "10008", "10009", "10010"}
