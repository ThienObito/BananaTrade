"""Adaptive paper trader with rolling performance controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol

from ..agents.execution.auto_trader import AutoTradeDecision, AutoTrader
from ..engine.entry_optimizer import EntryOptimizer
from ..engine.execution_model import ExecutionModel
from ..engine.mtf_signal import MultiTimeframeSignal
from ..engine.regime_detector import Regime, RegimeDetector
from ..engine.strategy import MACrossStrategy, SignalResult
from ..engine.trade_journal import TradeJournal
from ..risk_manager import RiskManager


class SignalStrategy(Protocol):
    """Strategy protocol accepted by adaptive execution."""

    def generate_signal(self, candles: Sequence[dict[str, object]]) -> SignalResult:
        """Generate signal from candle history."""
        ...


class AdaptiveTrader:
    """Wrap signal, execution, risk, and journal components for paper trading."""

    def __init__(
        self,
        trader: AutoTrader,
        risk_manager: RiskManager | None = None,
        execution_model: ExecutionModel | None = None,
        regime_detector: RegimeDetector | None = None,
        strategy: SignalStrategy | None = None,
        journal: TradeJournal | None = None,
        mtf_signal: MultiTimeframeSignal | object | None = None,
        entry_optimizer: EntryOptimizer | None = None,
        *,
        confidence_threshold: float = 0.65,
        risk_pct: float = 0.01,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if risk_pct < 0:
            raise ValueError("risk_pct must be non-negative")
        self.trader = trader
        self.broker = trader.broker
        self.symbol = trader.symbol
        self.risk_manager = risk_manager or RiskManager()
        self.execution_model = execution_model or ExecutionModel(trader.broker.initial_cash, risk_pct)
        self.regime_detector = regime_detector or RegimeDetector()
        self.strategy = strategy or MACrossStrategy()
        self.journal = journal or TradeJournal()
        self.mtf_signal = mtf_signal or MultiTimeframeSignal(self.strategy)
        self.entry_optimizer = entry_optimizer or EntryOptimizer()
        self.pending_limit_orders: list[dict[str, object]] = []
        self.partial_exits_today = 0
        self.use_limit_entries = entry_optimizer is not None or execution_model is None
        self._bar_number = 0
        self._expired_limit_order_this_bar = False
        self.base_confidence_threshold = confidence_threshold
        self.base_risk_pct = float(risk_pct)
        self._trades: list[bool] = []
        self._consecutive_losses = 0
        self._reduced_trades_remaining = 0
        self._last_signal: SignalResult | None = None
        self._last_regime: Regime | None = None

    def record_partial_exit(self) -> None:
        """Increment daily partial-exit count for dashboard reporting."""
        self.partial_exits_today += 1

    @property
    def rolling_win_rate(self) -> float:
        """Win rate over most recent 20 completed trade outcomes."""
        recent = self._trades[-20:]
        return sum(recent) / len(recent) if recent else 0.0

    @property
    def consecutive_losses(self) -> int:
        """Current consecutive losing-trade count."""
        return self._consecutive_losses

    @property
    def effective_confidence_threshold(self) -> float:
        """Confidence gate raised after poor rolling performance."""
        return 0.75 if self._trades and self.rolling_win_rate < 0.40 else self.base_confidence_threshold

    @property
    def effective_risk_pct(self) -> float:
        """Risk percentage, halved for five trades after three losses."""
        return self.base_risk_pct * 0.5 if self._reduced_trades_remaining > 0 else self.base_risk_pct

    @property
    def last_signal(self) -> SignalResult | None:
        return self._last_signal

    @property
    def last_regime(self) -> Regime | None:
        return self._last_regime

    def record_trade_result(self, won: bool) -> None:
        """Record completed outcome and activate or advance adaptive controls."""
        self._trades.append(bool(won))
        if won:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1
            if self._consecutive_losses >= 3 and self._reduced_trades_remaining == 0:
                self._reduced_trades_remaining = 5
        if self._reduced_trades_remaining > 0:
            self._reduced_trades_remaining -= 1

    def run_once(self, state: Mapping[str, object], candles: Sequence[dict[str, object]]) -> AutoTradeDecision:
        """Generate, adapt, execute, and journal one paper-trading decision."""
        candle_records = [dict(candle) for candle in candles]
        self._bar_number += 1
        self._expire_limit_orders()
        expired_this_bar = self._expired_limit_order_this_bar
        try:
            self._last_regime = self.regime_detector.detect(candle_records)
        except ValueError:
            self._last_regime = Regime.RANGING
        signal = self.strategy.generate_signal(candle_records)
        self._last_signal = signal
        if signal.confidence < self.effective_confidence_threshold:
            decision = self._skip("confidence below adaptive threshold")
        elif not self._mtf_confirm(candle_records):
            decision = self._skip("multi-timeframe confirmation failed")
        else:
            limit_entry = (
                self.entry_optimizer.compute_limit_entry(signal, candle_records, self._last_regime)
                if self.use_limit_entries
                else None
            )
            if limit_entry is None:
                params = self.execution_model.compute_entry(
                    signal,
                    candle_records,
                    self._last_regime,
                    equity=self._equity(state, candle_records),
                    risk_pct=self.effective_risk_pct,
                    entry_price=None,
                )
                if params is None:
                    decision = self._skip("execution model skipped signal")
                else:
                    decision = self.trader.run_once(
                        state,
                        {"bias": signal.bias, "confidence": signal.confidence, "price": params.price, "stale": False},
                        stop_loss=params.sl,
                        take_profit=params.tp,
                        quantity=float(params.qty),
                    )
            elif not self.pending_limit_orders and not expired_this_bar:
                self.pending_limit_orders.append(
                    {"price": limit_entry.price, "expiry_bar": self._bar_number + limit_entry.expiry_bars - 1, "bias": signal.bias}
                )
                decision = self._skip("limit entry pending")
            else:
                decision = self._skip("limit entry already pending")
        self.journal.append(self._journal_row(signal, decision))
        return decision

    def status(self) -> dict[str, object]:
        """Return dashboard-safe adaptive state."""
        return {
            "rolling_win_rate": self.rolling_win_rate,
            "consecutive_losses": self.consecutive_losses,
            "effective_confidence_threshold": self.effective_confidence_threshold,
            "effective_risk_pct": self.effective_risk_pct,
            "regime": self._last_regime.value if self._last_regime is not None else None,
            "last_signal": self._last_signal.bias if self._last_signal is not None else None,
            "pending_limit_orders": len(self.pending_limit_orders),
            "partial_exits_today": self.partial_exits_today,
        }

    def _expire_limit_orders(self) -> None:
        before = len(self.pending_limit_orders)
        self.pending_limit_orders = [
            order
            for order in self.pending_limit_orders
            if self._bar_number <= self._number(order.get("expiry_bar", 0))
        ]
        self._expired_limit_order_this_bar = len(self.pending_limit_orders) < before

    def _mtf_confirm(self, candles: list[dict[str, object]]) -> bool:
        confirm = getattr(self.mtf_signal, "confirm", None)
        if not callable(confirm):
            raise TypeError("mtf_signal must provide confirm")
        result = confirm(candles)
        return isinstance(result, bool) and result

    @staticmethod
    def _skip(reason: str) -> AutoTradeDecision:
        return {"action": "NONE", "reason": reason, "order_id": None}

    @staticmethod
    def _number(value: object) -> float:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0

    @staticmethod
    def _equity(state: Mapping[str, object], candles: Sequence[dict[str, object]]) -> float:
        value = state.get("equity")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
        close = candles[-1].get("close") if candles else 0.0
        return float(close) if isinstance(close, (int, float)) and close > 0 else 1.0

    def _journal_row(self, signal: SignalResult, decision: AutoTradeDecision) -> dict[str, object]:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "symbol": self.trader.symbol,
            "side": decision["action"],
            "entry": "",
            "exit": "",
            "sl": "",
            "tp": "",
            "qty": "",
            "pnl": "",
            "reason": f"{signal.reason}; {decision['reason']}",
        }

    @property
    def strategy_protocol(self) -> SignalStrategy:
        """Return configured signal strategy."""
        return self.strategy
