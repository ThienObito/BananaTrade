"""Decision brain shared by research and broker execution paths."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Literal

from .engine.adaptive_trader import AdaptiveTrader
from .engine.ensemble_signal import EnsembleSignal
from .engine.execution_model import ExecutionModel
from .engine.regime_detector import Regime, RegimeDetector
from .engine.strategy import SignalResult
from .risk_manager import RiskManager

DecisionSide = Literal["BUY", "SELL", "NONE"]
DECISION_COLUMNS = (
    "timestamp",
    "symbol",
    "side",
    "confidence",
    "entry",
    "sl",
    "tp",
    "volume",
    "reasons",
)


@dataclass
class Decision:
    """One auditable brain decision, including explicit no-trade reasons."""

    side: DecisionSide
    confidence: float
    entry: float | None
    sl: float | None
    tp: float | None
    volume: float
    reasons: list[str] = field(default_factory=list)

    @property
    def is_trade(self) -> bool:
        """Return whether decision authorizes directional execution."""
        return self.side != "NONE"

    def as_dict(self) -> dict[str, object]:
        """Return JSON/CSV-safe owned values."""
        return {
            "side": self.side,
            "confidence": self.confidence,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "volume": self.volume,
            "reasons": list(self.reasons),
        }


def decide(
    candles: Sequence[Mapping[str, object]],
    symbol_spec: Mapping[str, object] | object,
    account_state: Mapping[str, object] | object,
    **kwargs: object,
) -> Decision:
    """Build one default brain and return one logged decision."""
    threshold = kwargs.get("confidence_threshold", 0.65)
    max_spread = kwargs.get("max_spread")
    log_path = kwargs.get("decision_log_path", "trades/decisions.csv")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        raise TypeError("confidence_threshold must be numeric")
    if max_spread is not None and (not isinstance(max_spread, (int, float)) or isinstance(max_spread, bool)):
        raise TypeError("max_spread must be numeric")
    if not isinstance(log_path, (str, Path)):
        raise TypeError("decision_log_path must be a path")
    return Brain(confidence_threshold=float(threshold), max_spread=float(max_spread) if max_spread is not None else None, decision_log_path=log_path).decide(candles, symbol_spec, account_state)


class Brain:
    """Combine signal, regime, execution, and account risk before any broker call."""

    def __init__(
        self,
        *,
        regime_detector: RegimeDetector | None = None,
        ensemble: EnsembleSignal | None = None,
        execution_model: ExecutionModel | None = None,
        risk_manager: RiskManager | None = None,
        adaptive_trader: AdaptiveTrader | None = None,
        confidence_threshold: float = 0.65,
        max_spread: float | None = None,
        decision_log_path: str | Path = "trades/decisions.csv",
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if max_spread is not None and (not isfinite(max_spread) or max_spread < 0):
            raise ValueError("max_spread must be non-negative and finite")
        detector = regime_detector or (ensemble.regime_detector if ensemble is not None else RegimeDetector())
        self.regime_detector = detector
        self.ensemble = ensemble or EnsembleSignal(regime_detector=detector)
        self.execution_model = execution_model or ExecutionModel()
        self.risk_manager = risk_manager or RiskManager()
        self.adaptive_trader = adaptive_trader
        self.confidence_threshold = confidence_threshold
        self.max_spread = max_spread
        self.decision_log_path = Path(decision_log_path)
        self.last_decision: Decision | None = None

    def decide(
        self,
        candles: Sequence[Mapping[str, object]],
        symbol_spec: Mapping[str, object] | object,
        account_state: Mapping[str, object] | object,
    ) -> Decision:
        """Produce and log one decision without sending an order."""
        records = [dict(candle) for candle in candles]
        symbol = str(_field(symbol_spec, "name", _field(symbol_spec, "symbol", "")))
        reasons: list[str] = []
        confidence = 0.0
        entry: float | None = None
        try:
            score = self.ensemble.score(records)
            confidence = _finite_non_negative(score.confidence)
        except (TypeError, ValueError, KeyError) as exc:
            reasons.append(f"signal calculation failed: {exc}")
            return self._finish(symbol, Decision("NONE", confidence, None, None, None, 0.0, reasons))

        threshold = self._confidence_threshold()
        regime = self.regime_detector.last_regime
        if regime is None:
            try:
                regime = self.regime_detector.detect(records)
            except (TypeError, ValueError):
                regime = Regime.RANGING
        if confidence < threshold:
            reasons.append(f"confidence {confidence:.4f} below threshold {threshold:.4f}")
        if regime is Regime.VOLATILE:
            reasons.append("VOLATILE regime")
        spread = self._spread(symbol_spec, account_state)
        max_spread = self._max_spread(symbol_spec)
        if max_spread is not None and spread > max_spread:
            reasons.append(f"spread {spread:.8f} exceeds max_spread {max_spread:.8f}")
        if score.bias == "NEUTRAL":
            reasons.append("ensemble signal is NEUTRAL")
        if reasons:
            return self._finish(symbol, Decision("NONE", confidence, None, None, None, 0.0, reasons))

        side: DecisionSide = "BUY" if score.bias == "LONG" else "SELL"
        entry = self._entry_price(side, records, symbol_spec, account_state)
        if entry is None:
            return self._finish(symbol, Decision("NONE", confidence, None, None, None, 0.0, ["missing valid entry price"]))
        signal = SignalResult(score.bias, confidence, "; ".join(score.components.keys()))
        equity = _number(_field(account_state, "equity", 0.0))
        risk_pct = self._risk_pct()
        params = self.execution_model.compute_entry(
            signal,
            records,
            regime,
            equity=equity,
            risk_pct=risk_pct,
            entry_price=entry,
        )
        if params is None:
            return self._finish(symbol, Decision("NONE", confidence, None, None, None, 0.0, ["execution model rejected signal"]))
        volume = self._volume(params.qty, params.price, symbol_spec)
        proposed_size = params.price * volume
        risk = self.risk_manager.check_can_open(
            equity,
            _number(_field(account_state, "daily_pnl", 0.0)),
            self._open_count(account_state),
            proposed_size,
        )
        if not risk.allowed:
            return self._finish(symbol, Decision("NONE", confidence, None, None, None, 0.0, [f"risk check failed: {risk.reason}"]))
        reasons = [f"{regime.value} regime", "confidence gate passed", "risk checks passed"]
        return self._finish(
            symbol,
            Decision(
                side,
                confidence,
                self._round_price(params.price, symbol_spec),
                self._round_price(params.sl, symbol_spec),
                self._round_price(params.tp, symbol_spec),
                volume,
                reasons,
            ),
        )

    def _finish(self, symbol: str, decision: Decision) -> Decision:
        self.last_decision = decision
        self._log(symbol, decision)
        return decision

    def _confidence_threshold(self) -> float:
        if self.adaptive_trader is None:
            return self.confidence_threshold
        return max(self.confidence_threshold, self.adaptive_trader.effective_confidence_threshold)

    def _risk_pct(self) -> float:
        if self.adaptive_trader is None:
            return self.execution_model.risk_pct
        return self.adaptive_trader.effective_risk_pct

    def _max_spread(self, symbol_spec: Mapping[str, object] | object) -> float | None:
        value = self.max_spread if self.max_spread is not None else _field(symbol_spec, "max_spread", None)
        if value is None:
            return None
        return _number(value)

    @staticmethod
    def _spread(symbol_spec: Mapping[str, object] | object, account_state: Mapping[str, object] | object) -> float:
        direct = _field(symbol_spec, "spread", _field(account_state, "spread", None))
        if direct is not None:
            return max(0.0, _number(direct))
        bid = _number(_field(account_state, "bid", 0.0))
        ask = _number(_field(account_state, "ask", 0.0))
        return max(0.0, ask - bid) if ask >= bid > 0 else 0.0

    @staticmethod
    def _entry_price(
        side: DecisionSide,
        candles: Sequence[Mapping[str, object]],
        symbol_spec: Mapping[str, object] | object,
        account_state: Mapping[str, object] | object,
    ) -> float | None:
        field = "ask" if side == "BUY" else "bid"
        value = _field(account_state, field, _field(symbol_spec, field, None))
        if value is None:
            value = candles[-1].get("close") if candles else None
        number = _number(value)
        return number if number > 0 else None

    @staticmethod
    def _open_count(account_state: Mapping[str, object] | object) -> int:
        value = _field(account_state, "open_count", None)
        if value is not None:
            return max(0, int(_number(value)))
        positions = _field(account_state, "positions", ())
        return len(positions) if isinstance(positions, (list, tuple, set, frozenset, dict)) else 0

    @staticmethod
    def _volume(raw: float, price: float, symbol_spec: Mapping[str, object] | object) -> float:
        minimum = max(0.0, _number(_field(symbol_spec, "volume_min", 0.0)))
        maximum = _number(_field(symbol_spec, "volume_max", raw)) or raw
        step = _number(_field(symbol_spec, "volume_step", minimum or 1.0)) or 1.0
        volume = min(maximum, max(minimum, raw))
        rounded = minimum + (max(0.0, volume - minimum) // step) * step
        return round(max(minimum, rounded), 8) if price > 0 else 0.0

    @staticmethod
    def _round_price(value: float, symbol_spec: Mapping[str, object] | object) -> float:
        digits = int(_number(_field(symbol_spec, "digits", 8)))
        return round(value, max(0, min(12, digits)))

    def _log(self, symbol: str, decision: Decision) -> None:
        self.decision_log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.decision_log_path.exists() or self.decision_log_path.stat().st_size == 0
        with self.decision_log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "symbol": symbol,
                    "side": decision.side,
                    "confidence": decision.confidence,
                    "entry": decision.entry if decision.entry is not None else "",
                    "sl": decision.sl if decision.sl is not None else "",
                    "tp": decision.tp if decision.tp is not None else "",
                    "volume": decision.volume,
                    "reasons": " | ".join(decision.reasons),
                },
            )


def _field(source: Mapping[str, object] | object, name: str, default: object) -> object:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(float(value)):
        return 0.0
    return float(value)


def _finite_non_negative(value: object) -> float:
    number = _number(value)
    return max(0.0, number)
