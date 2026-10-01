import math

from bananatrade.evaluation.metrics import (
    annualized_return, exposure_time, expectancy_r, max_drawdown,
    max_drawdown_duration, profit_factor, sharpe_ratio, sortino_ratio,
    total_return, trade_count, volatility, win_rate,
)


def test_return_metrics():
    # Compounded: 1.1 * 0.9 - 1 = -0.01 (not 0); see total_return docstring.
    assert math.isclose(total_return([.1, -.1]), -.01)
    assert math.isclose(annualized_return([.1], 2), .21)


def test_risk_metrics_hand_computed():
    assert math.isclose(volatility([.0, .1, .2]), .1)
    assert math.isclose(sharpe_ratio([.0, .1, .2]), 1.0)
    assert math.isclose(sortino_ratio([-.1, .1, .2]), 1.1547005383792517)
    assert max_drawdown([100, 120, 90, 110]) == -.25
    assert max_drawdown_duration([100, 120, 90, 80, 130]) == 2


def test_trade_metrics():
    trades = [2, -1, 3, -2]
    assert win_rate(trades) == .5
    assert profit_factor(trades) == 5 / 3
    assert expectancy_r(trades) == .5
    assert exposure_time([True, False, True, True]) == .75
    assert trade_count(trades) == 4


def test_empty_and_degenerate_are_finite():
    funcs = [lambda: total_return([]), lambda: annualized_return([], 1),
             lambda: volatility([1]), lambda: sharpe_ratio([1]), lambda: sortino_ratio([1]),
             lambda: max_drawdown([]), lambda: max_drawdown_duration([]), lambda: win_rate([]),
             lambda: profit_factor([-1, -2]), lambda: expectancy_r([]), lambda: exposure_time([])]
    assert all(math.isfinite(float(fn())) for fn in funcs)
    assert sharpe_ratio([1, 1]) == 0
    assert sortino_ratio([1, 1]) == 0
    assert total_return([]) == 0
