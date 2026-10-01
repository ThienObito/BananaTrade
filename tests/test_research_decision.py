from dataclasses import replace

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.research.decision import decide_default
from bananatrade.research.entry_ablation import Dataset, run_research


def fixture_reports():
    candles = tuple({"open": 100.0 + i * 0.1, "high": 101.0 + i * 0.1, "low": 99.0 + i * 0.1, "close": 100.0 + i * 0.1, "volume": 1.0, "atr14": 1.0} for i in range(250))
    return run_research((Dataset("BTCUSDT", "1h", candles),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3).reports


def test_default_is_no_proven_edge_without_all_evidence() -> None:
    decision = decide_default(fixture_reports(), 1)
    assert decision.status == "NO PROVEN EDGE"
    assert decision.selected_variant is None


def test_positive_ci_and_random_gate_can_select_variant() -> None:
    reports = fixture_reports()
    selected = replace(reports[0], expectancy_ci_low=0.1, mean_net_return_pct=10.0, random_p90_return_pct=1.0, insufficient=False)
    decision = decide_default((selected,), 1)
    assert decision.selected_variant == selected.variant
    assert decision.dataset_count == 1
    assert decision.gate_evidence[0].passed


def test_negative_ci_blocks_variant() -> None:
    report = replace(fixture_reports()[0], expectancy_ci_low=0.0, mean_net_return_pct=10.0, random_p90_return_pct=1.0, insufficient=False)
    decision = decide_default((report,), 1)
    assert decision.status == "NO PROVEN EDGE"


def test_random_percentile_gate_blocks_variant() -> None:
    report = replace(fixture_reports()[0], expectancy_ci_low=0.1, mean_net_return_pct=1.0, random_p90_return_pct=1.0, insufficient=False)
    assert decide_default((report,), 1).selected_variant is None


def test_insufficient_gate_blocks_variant() -> None:
    report = replace(fixture_reports()[0], expectancy_ci_low=0.1, mean_net_return_pct=10.0, random_p90_return_pct=1.0, insufficient=True)
    assert decide_default((report,), 1).selected_variant is None


def test_three_of_four_positive_datasets_can_select_variant() -> None:
    reports = list(fixture_reports())
    base = reports[0]
    evidence = tuple(replace(base, dataset=f"D{index}", expectancy_ci_low=0.1, mean_net_return_pct=10.0, random_p90_return_pct=1.0, insufficient=False) for index in range(4))
    blocked = replace(evidence[3], expectancy_ci_low=-0.1, mean_net_return_pct=-1.0)
    decision = decide_default(evidence[:3] + (blocked,), 4)
    assert decision.selected_variant == base.variant


def test_missing_dataset_evidence_blocks_variant() -> None:
    report = replace(fixture_reports()[0], expectancy_ci_low=0.1, mean_net_return_pct=10.0, random_p90_return_pct=1.0, insufficient=False)
    with pytest.raises(ValueError, match="does not match"):
        decide_default((report,), 2)


def test_invalid_dataset_count_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        decide_default((), 0)
