"""Evidence-gated default selection for entry research."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .entry_ablation import VariantReport


@dataclass(frozen=True)
class GateEvidence:
    """Per-variant evidence gates for audit output."""

    variant: str
    dataset_count: int
    required_dataset_count: int
    dataset_names: tuple[str, ...]
    complete_dataset_evidence: bool
    positive_expectancy_ci: bool
    beats_random_p90: bool
    sufficient_trades: bool
    passed: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    """Final research decision and exact reason."""

    selected_variant: str | None
    status: str
    reason: str
    dataset_count: int = 0
    dataset_names: tuple[str, ...] = ()
    gate_evidence: tuple[GateEvidence, ...] = ()


def decide_default(reports: Sequence[VariantReport], dataset_count: int | None = None) -> Decision:
    """Select only variant with positive CI and random-beating evidence."""
    names = tuple(sorted({report.dataset for report in reports}))
    if dataset_count is not None and dataset_count <= 0:
        raise ValueError("dataset_count must be positive")
    if not names:
        return Decision(None, "NO PROVEN EDGE", "No research reports supplied.")
    report_names = [report.dataset for report in reports]
    if len(report_names) != len(set(report_names)) and len({report.variant for report in reports}) == 1:
        raise ValueError("duplicate dataset evidence")
    required_count = len(names)
    if dataset_count is not None and dataset_count != required_count:
        raise ValueError("dataset_count does not match report dataset identities")
    required_positive = 3 if required_count == 4 else required_count
    evidence_rows: list[GateEvidence] = []
    candidates: list[str] = []
    for variant in sorted({report.variant for report in reports}):
        evidence = [report for report in reports if report.variant == variant]
        evidence_names = tuple(sorted(report.dataset for report in evidence))
        reasons: list[str] = []
        complete = len(evidence) == required_count and len(set(evidence_names)) == required_count and set(evidence_names) == set(names)
        positive_count = sum(report.expectancy_ci_low > 0 for report in evidence)
        random_count = sum(report.mean_net_return_pct > report.random_p90_return_pct for report in evidence)
        sufficient_count = sum(not report.insufficient for report in evidence)
        positive_ci = complete and positive_count >= required_positive
        beats_random = complete and random_count >= required_positive
        sufficient = complete and sufficient_count >= required_positive
        if not complete:
            reasons.append("missing_or_duplicate_dataset_evidence")
        if not positive_ci:
            reasons.append(f"positive_ci_on_{positive_count}_of_{required_count}_datasets")
        if not beats_random:
            reasons.append(f"random_p90_gate_on_{random_count}_of_{required_count}_datasets")
        if not sufficient:
            reasons.append(f"sufficient_trades_on_{sufficient_count}_of_{required_count}_datasets")
        passed = complete and positive_ci and beats_random and sufficient
        evidence_rows.append(GateEvidence(variant, len(evidence), required_count, evidence_names, complete, positive_ci, beats_random, sufficient, passed, tuple(reasons)))
        if passed:
            candidates.append(variant)
    if not candidates:
        return Decision(None, "NO PROVEN EDGE", f"No variant passed gates on at least {required_positive} of {required_count} datasets.", required_count, names, tuple(evidence_rows))
    selected = candidates[0]
    return Decision(selected, "PROVEN EDGE", f"{selected} passed all evidence gates on {required_count} datasets.", required_count, names, tuple(evidence_rows))
