"""Deterministic pre-trade risk checks."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .limits import RiskLimits, load_limits


@dataclass(frozen=True)
class ProposalInput:
    side: str
    entry: float
    stop_loss: Optional[float]
    take_profit: float
    size_pct: float


@dataclass(frozen=True)
class RiskState:
    equity: float
    peak_equity: float
    open_exposure_pct: float
    daily_pnl_pct: float
    trades_today: int
    consecutive_losses: int
    last_loss_at: Optional[datetime] = None


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reasons: tuple[str, ...] = ()
    adjusted_size_pct: Optional[float] = None


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None, config_path: str = "config/risk.yaml") -> None:
        self.limits = limits or load_limits(config_path)
        self._kill_switch = False

    def reset_kill_switch(self) -> None:
        self._kill_switch = False

    def check(self, proposal: ProposalInput, state: RiskState, now: datetime | None = None) -> RiskResult:
        now = now or datetime.now()
        l, reasons = self.limits, []
        side = proposal.side.upper()
        if self._kill_switch or (state.peak_equity > 0 and (state.peak_equity - state.equity) / state.peak_equity >= l.max_drawdown_pct):
            self._kill_switch = True
            reasons.append("kill_switch")
        if state.daily_pnl_pct <= -l.max_daily_loss_pct: reasons.append("max_daily_loss")
        if state.trades_today >= l.max_trades_per_day: reasons.append("max_trades_per_day")
        if state.consecutive_losses >= l.cooldown_after_losses and state.last_loss_at and now < state.last_loss_at + timedelta(minutes=l.cooldown_minutes):
            reasons.append("cooldown_after_losses")
        if side not in ("LONG", "SHORT"): reasons.append("invalid_side")
        if proposal.size_pct <= 0: reasons.append("invalid_size")
        if proposal.stop_loss is None and l.require_stop_loss: reasons.append("missing_stop_loss")
        if proposal.stop_loss is not None:
            valid_stop = (side == "LONG" and proposal.stop_loss < proposal.entry) or (side == "SHORT" and proposal.stop_loss > proposal.entry)
            if not valid_stop: reasons.append("wrong_side_stop")
        if side in ("LONG", "SHORT") and proposal.stop_loss is not None:
            risk = abs(proposal.entry - proposal.stop_loss)
            reward = (proposal.take_profit - proposal.entry) if side == "LONG" else (proposal.entry - proposal.take_profit)
            if risk <= 0 or reward / risk < l.min_reward_risk: reasons.append("min_reward_risk")
        allowed = min(l.max_position_pct, max(0.0, l.max_total_exposure_pct - state.open_exposure_pct))
        adjusted = min(proposal.size_pct, allowed)
        # Oversized requests are safely clipped rather than rejected; the engine
        # never increases a requested size.  A completely exhausted exposure
        # budget remains a hard rejection.
        if adjusted <= 0: reasons.append("max_total_exposure_pct")
        if reasons: return RiskResult(False, tuple(reasons), None)
        return RiskResult(True, (), adjusted)
