"""Account-level position and loss limits for paper trading."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RiskCheckResult:
    """Result of one proposed paper-position risk check."""

    allowed: bool
    reason: str


class RiskManager:
    """Apply simple account-level limits before opening paper positions."""

    def __init__(
        self,
        max_open_positions: int = 3,
        max_daily_loss_pct: float = 0.02,
        max_position_size_pct: float = 0.10,
    ) -> None:
        if max_open_positions < 0:
            raise ValueError("max_open_positions must be non-negative")
        if not 0 <= max_daily_loss_pct <= 1:
            raise ValueError("max_daily_loss_pct must be between 0 and 1")
        if not 0 <= max_position_size_pct <= 1:
            raise ValueError("max_position_size_pct must be between 0 and 1")
        self.max_open_positions = max_open_positions
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_pct = max_position_size_pct

    def check_can_open(
        self,
        equity: float,
        daily_pnl: float,
        open_count: int,
        proposed_size: float,
    ) -> RiskCheckResult:
        """Return whether one proposed paper position satisfies all limits."""
        if not self._finite_positive(equity):
            return RiskCheckResult(False, "equity must be positive and finite")
        if not isfinite(daily_pnl):
            return RiskCheckResult(False, "daily_pnl must be finite")
        if open_count < 0:
            return RiskCheckResult(False, "open_count must be non-negative")
        if not self._finite_non_negative(proposed_size):
            return RiskCheckResult(False, "proposed_size must be non-negative and finite")
        if open_count >= self.max_open_positions:
            return RiskCheckResult(False, "maximum open positions reached")
        if daily_pnl / equity <= -self.max_daily_loss_pct:
            return RiskCheckResult(False, "daily loss limit exceeded")
        if proposed_size / equity > self.max_position_size_pct:
            return RiskCheckResult(False, "maximum position size exceeded")
        return RiskCheckResult(True, "risk checks passed")

    def check_drawdown(self, equity: float, peak_equity: float) -> bool:
        """Return whether drawdown is above 10 percent and trading must halt."""
        if not self._finite_positive(equity) or not self._finite_positive(peak_equity):
            return True
        return (peak_equity - equity) / peak_equity > 0.10

    @staticmethod
    def _finite_positive(value: float) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0

    @staticmethod
    def _finite_non_negative(value: float) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0
