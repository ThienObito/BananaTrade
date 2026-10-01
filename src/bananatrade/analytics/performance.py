"""Metrics for closed paper-trade journal rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from statistics import mean, pstdev


@dataclass(frozen=True)
class PerformanceMetrics:
    """Summary statistics computed from closed journal trades."""

    total_trades: int
    win_rate: float
    profit_factor: float
    avg_r_multiple: float
    expectancy_r: float
    max_drawdown_pct: float
    sharpe: float
    longest_losing_streak: int

    def as_dict(self) -> dict[str, object]:
        """Return JSON-ready metrics."""
        return asdict(self)


def compute_metrics(journal_rows: Iterable[Mapping[str, object]]) -> PerformanceMetrics:
    """Compute deterministic trade metrics; empty or malformed rows are ignored."""
    trades: list[tuple[float, float]] = []
    for row in journal_rows:
        pnl = _number(row.get("pnl"))
        if pnl is None:
            continue
        risk = _risk(row)
        trades.append((pnl, risk))
    if not trades:
        return PerformanceMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

    r_values = [pnl / risk if risk > 0 else pnl for pnl, risk in trades]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    gross_profit = sum(value for value in wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    equity = 1.0
    peak = equity
    max_drawdown = 0.0
    equity_points = [equity]
    for value in r_values:
        equity = max(0.0, equity + value)
        equity_points.append(equity)
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
    returns = [equity_points[index] / equity_points[index - 1] - 1.0 for index in range(1, len(equity_points)) if equity_points[index - 1] > 0]
    deviation = pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = mean(returns) / deviation * sqrt(252) if deviation > 0 and len(set(returns)) > 1 and len(set(r_values)) > 1 else 0.0
    return PerformanceMetrics(
        total_trades=len(trades),
        win_rate=len(wins) / len(trades),
        profit_factor=profit_factor,
        avg_r_multiple=mean(r_values),
        expectancy_r=mean(r_values),
        max_drawdown_pct=max_drawdown,
        sharpe=sharpe,
        longest_losing_streak=_longest_losing_streak(r_values),
    )


def _risk(row: Mapping[str, object]) -> float:
    entry = _number(row.get("entry"))
    stop = _number(row.get("sl", row.get("stop_loss")))
    if entry is not None and stop is not None and abs(entry - stop) > 0:
        return abs(entry - stop) * max(_number(row.get("qty")) or 1.0, 0.0)
    return 1.0


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _longest_losing_streak(values: list[float]) -> int:
    longest = current = 0
    for value in values:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
