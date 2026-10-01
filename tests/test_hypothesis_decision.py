from dataclasses import replace

import pytest

from bananatrade.research.hypothesis_decision import decide_hypothesis_default
from bananatrade.research.hypothesis_research import HypothesisResult


def result(dataset: str, *, ci: float = 0.1, mean_return: float = 2.0, random_p90: float = 1.0, insufficient: bool = False) -> HypothesisResult:
    return HypothesisResult(dataset, "H1", "fixed_2r", (), 40, mean_return, 0.2, ci, 0.4, 1.0, 0.5, 55.0, 1.2, 10.0, 1.0, 0.2, 0.1, random_p90, 12, insufficient)


def test_three_of_four_sets_can_pass() -> None:
    reports = (result("BTC15"), result("BTC1h"), result("ETH15"), result("ETH1h", ci=-0.1, mean_return=-1.0))
    decision = decide_hypothesis_default(reports, 4)
    assert decision.status == "PROVEN EDGE"
    assert decision.selected_variant == "H1/fixed_2r"


def test_ci_gate_requires_positive_lower_bound() -> None:
    reports = tuple(result(name, ci=-0.1) for name in ("A", "B", "C", "D"))
    assert decide_hypothesis_default(reports, 4).status == "NO PROVEN EDGE"


def test_random_p90_gate_requires_strict_outperformance() -> None:
    reports = tuple(result(name, mean_return=1.0, random_p90=1.0) for name in ("A", "B", "C", "D"))
    assert decide_hypothesis_default(reports, 4).status == "NO PROVEN EDGE"


def test_insufficient_sets_block_selection() -> None:
    reports = tuple(result(name, insufficient=True) for name in ("A", "B", "C", "D"))
    assert decide_hypothesis_default(reports, 4).status == "NO PROVEN EDGE"


def test_missing_dataset_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not match"):
        decide_hypothesis_default((result("A"),), 4)


def test_invalid_dataset_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        decide_hypothesis_default((), 0)


def test_selected_combination_uses_best_ci_lower_bound() -> None:
    first = result("A", ci=0.2)
    second = replace(first, hypothesis="H2", ci_low=0.4)
    reports = (first, second) * 4
    reports = tuple(replace(item, dataset=chr(65 + index // 2)) for index, item in enumerate(reports))
    decision = decide_hypothesis_default(reports, 4)
    assert decision.selected_variant == "H2/fixed_2r"
