"""Evidence gate for hypothesis and exit combinations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .hypothesis_research import HypothesisResult


@dataclass(frozen=True)
class HypothesisDecision:
    selected_variant: str | None
    status: str
    reason: str
    dataset_count: int
    positive_ci_datasets: int
    random_gate_datasets: int


def decide_hypothesis_default(results: Sequence[HypothesisResult], dataset_count: int) -> HypothesisDecision:
    if dataset_count <= 0:
        raise ValueError("dataset_count must be positive")
    names = {result.dataset for result in results}
    if len(names) != dataset_count:
        raise ValueError("dataset_count does not match result dataset identities")
    required = 3 if dataset_count == 4 else dataset_count
    candidates: list[tuple[float, HypothesisResult, int, int]] = []
    for key in sorted({result.key for result in results}):
        evidence = [result for result in results if result.key == key]
        positive = sum(result.ci_low > 0 for result in evidence)
        random_gate = sum(result.mean_net_return_pct > result.random_p90_return_pct for result in evidence)
        sufficient = sum(not result.insufficient for result in evidence)
        complete = len(evidence) == dataset_count and len({result.dataset for result in evidence}) == dataset_count
        if complete and positive >= required and random_gate >= required and sufficient >= required:
            representative = max(evidence, key=lambda result: result.ci_low)
            candidates.append((representative.ci_low, representative, positive, random_gate))
    if not candidates:
        return HypothesisDecision(None, "NO PROVEN EDGE", f"No hypothesis/exit combination passed gates on at least {required} of {dataset_count} datasets.", dataset_count, 0, 0)
    _, selected, positive, random_gate = max(candidates, key=lambda item: item[0])
    return HypothesisDecision(selected.key, "PROVEN EDGE", f"{selected.key} passed CI, random-entry, and trade-count gates on at least {required} datasets.", dataset_count, positive, random_gate)
