"""Pure, finite performance metrics for returns and trades."""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def _finite(value: float, default: float = 0.0) -> float:
    return value if math.isfinite(value) else default


def total_return(values: Iterable[float]) -> float:
    """Compound periodic returns; empty input returns 0."""
    result = 1.0
    seen = False
    for value in values:
        seen = True
        result *= 1.0 + float(value)
    return _finite(result - 1.0 if seen else 0.0)


def annualized_return(values: Sequence[float], bars_per_year: float) -> float:
    """Annualized compound return from periodic returns."""
    if not values or bars_per_year <= 0 or not math.isfinite(bars_per_year):
        return 0.0
    growth = 1.0 + total_return(values)
    if growth < 0:
        return 0.0
    return _finite(growth ** (bars_per_year / len(values)) - 1.0)


def volatility(values: Sequence[float], annualize: float = 1.0) -> float:
    """Sample standard deviation, optionally annualized."""
    if len(values) < 2 or annualize <= 0:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return _finite(math.sqrt(max(0.0, variance) * annualize))


def sharpe_ratio(values: Sequence[float], risk_free: float = 0.0, annualize: float = 1.0) -> float:
    if len(values) < 2:
        return 0.0
    excess = [x - risk_free for x in values]
    sd = volatility(excess, annualize)
    return _finite((sum(excess) / len(excess)) / sd * math.sqrt(annualize)) if sd else 0.0


def sortino_ratio(values: Sequence[float], target: float = 0.0, annualize: float = 1.0) -> float:
    if not values or annualize <= 0:
        return 0.0
    downside = [min(0.0, x - target) for x in values]
    denom = math.sqrt(sum(x * x for x in downside) / len(values)) * math.sqrt(annualize)
    return _finite((sum(values) / len(values) - target) / denom * math.sqrt(annualize)) if denom else 0.0


def max_drawdown(equity: Sequence[float]) -> float:
    peak = None
    worst = 0.0
    for value in equity:
        peak = value if peak is None else max(peak, value)
        if peak:
            worst = min(worst, (value - peak) / peak)
    return _finite(worst)


def max_drawdown_duration(equity: Sequence[float]) -> int:
    peak = None; current = 0; longest = 0
    for value in equity:
        peak = value if peak is None else max(peak, value)
        if value < peak: current += 1; longest = max(longest, current)
        else: current = 0
    return longest


def win_rate(trades: Iterable[float]) -> float:
    data = list(trades); return _finite(sum(x > 0 for x in data) / len(data)) if data else 0.0


def profit_factor(trades: Iterable[float]) -> float:
    data = list(trades); losses = -sum(x for x in data if x < 0)
    return _finite(sum(x for x in data if x > 0) / losses) if losses else 0.0


def expectancy_r(trades: Iterable[float]) -> float:
    data = list(trades); return _finite(sum(data) / len(data)) if data else 0.0


def exposure_time(in_position: Iterable[bool]) -> float:
    data = list(in_position); return _finite(sum(bool(x) for x in data) / len(data)) if data else 0.0


def trade_count(trades: Iterable[object]) -> int:
    return len(list(trades))
