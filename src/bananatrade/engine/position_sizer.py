"""Fixed-risk paper position sizing."""
from __future__ import annotations

from math import floor, isfinite


class PositionSizer:
    """Size positions from equity and stop distance."""

    @staticmethod
    def compute_qty(
        equity: float,
        entry: float,
        stop_loss: float,
        risk_pct: float = 0.01,
    ) -> int:
        """Return at least one unit using fixed percentage account risk."""
        if not isfinite(equity) or equity <= 0 or entry <= 0 or stop_loss <= 0 or not isfinite(risk_pct) or risk_pct <= 0 or risk_pct > 1:
            raise ValueError("equity and risk_pct must be positive and prices must be finite")
        distance = abs(entry - stop_loss)
        if distance == 0:
            raise ValueError("entry and stop_loss must differ")
        return max(1, floor(equity * risk_pct / distance))
