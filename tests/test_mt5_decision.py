from __future__ import annotations

import json
from dataclasses import replace

import pytest

from bananatrade.research.entry_ablation import VariantReport
from bananatrade.research.hypothesis_research import HypothesisResult
from bananatrade.research.mt5_candidate import persist_candidate
from bananatrade.research.mt5_decision import MT5Decision, decide_mt5_entry, decide_mt5_hypothesis


def entry_report(dataset: str, *, ci: float = 0.1, mean_return: float = 2.0, random: float = 1.0) -> VariantReport:
    return VariantReport(
        dataset, "V0", (), 40, mean_return, mean_return, 0.2, ci, 0.5, 1.0, 55.0, 1.2,
        False, 0.0, random, 0.5, 510, 0.2, 0, 0.0, 0.0,
    )


def hypothesis_result(dataset: str, *, ci: float = 0.1, mean_return: float = 2.0, random: float = 1.0) -> HypothesisResult:
    return HypothesisResult(
        dataset, "H1", "fixed_2r", (), 40, mean_return, 0.2, ci, 0.4, 1.0, 0.5,
        55.0, 1.2, 10.0, 1.0, 0.2, mean_return, random, 40, False,
    )


def names() -> tuple[str, ...]:
    return tuple(f"S{index}" for index in range(8))


def test_mx_entry_requires_five_positive_ci_and_random_sets() -> None:
    reports = tuple(entry_report(name) for name in names())
    decision = decide_mt5_entry(reports)
    assert decision.status == "PROVEN EDGE"
    assert decision.selected_variant == "V0"
    assert decision.positive_ci_datasets == 8
    assert decision.random_gate_datasets == 8


def test_mx_entry_exact_status_when_unproven() -> None:
    reports = tuple(entry_report(name, ci=-0.1, mean_return=0.5, random=1.0) for name in names())
    decision = decide_mt5_entry(reports)
    assert decision.status == "NO PROVEN EDGE ON MT5 DATA"
    assert decision.selected_variant is None


def test_mx_entry_needs_complete_evidence() -> None:
    with pytest.raises(ValueError, match="identities"):
        decide_mt5_entry(tuple(entry_report(name) for name in names()[:-1]))


def test_mx_entry_accepts_five_sets() -> None:
    reports = []
    for index, name in enumerate(names()):
        reports.append(entry_report(name, ci=0.1 if index < 5 else -0.1, mean_return=2.0 if index < 5 else 0.5, random=1.0))
    assert decide_mt5_entry(tuple(reports)).status == "PROVEN EDGE"


def test_mx_entry_requires_same_dataset_for_both_gates() -> None:
    reports = []
    for index, name in enumerate(names()):
        reports.append(
            entry_report(
                name,
                ci=0.1 if index < 5 else -0.1,
                mean_return=2.0 if index >= 3 else 0.5,
                random=1.0,
            )
        )
    assert decide_mt5_entry(tuple(reports)).status == "NO PROVEN EDGE ON MT5 DATA"


def test_mx_entry_rejects_insufficient_datasets_below_threshold() -> None:
    reports = [entry_report(name) for name in names()]
    for index in range(4):
        reports[index] = replace(reports[index], insufficient=True)
    assert decide_mt5_entry(tuple(reports)).status == "NO PROVEN EDGE ON MT5 DATA"


def test_mx_hypothesis_gate_selects_key() -> None:
    decision = decide_mt5_hypothesis(tuple(hypothesis_result(name) for name in names()))
    assert decision.status == "PROVEN EDGE"
    assert decision.selected_variant == "H1/fixed_2r"


def test_mx_hypothesis_gate_rejects_insufficient_evidence() -> None:
    values = tuple(replace(hypothesis_result(name), ci_low=-0.1, mean_net_return_pct=0.0) for name in names())
    decision = decide_mt5_hypothesis(values)
    assert decision.status == "NO PROVEN EDGE ON MT5 DATA"


def test_mx_gate_rejects_wrong_configuration() -> None:
    with pytest.raises(ValueError, match="dataset_count"):
        decide_mt5_entry((), dataset_count=4)


def test_candidate_persistence_is_execution_off(tmp_path) -> None:
    target = tmp_path / "candidate.json"
    persist_candidate(MT5Decision("V0", "PROVEN EDGE", "ok", 8, 5, 5), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["candidate"] == "V0"
    assert payload["execution_enabled"] is False


def test_unproven_candidate_persists_explicit_no_edge_state(tmp_path) -> None:
    target = tmp_path / "x.json"
    persist_candidate(MT5Decision(None, "NO PROVEN EDGE ON MT5 DATA", "no", 8, 0, 0), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["candidate"] is None
    assert payload["status"] == "NO PROVEN EDGE ON MT5 DATA"
