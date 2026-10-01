"""MX-specific five-of-eight evidence gate."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .entry_ablation import VariantReport
from .hypothesis_research import HypothesisResult


@dataclass(frozen=True)
class MT5Decision:
    selected_variant: str | None
    status: str
    reason: str
    dataset_count: int
    positive_ci_datasets: int
    random_gate_datasets: int


def decide_mt5_entry(
    reports: Sequence[VariantReport], dataset_count: int = 8, minimum_sets: int = 5
) -> MT5Decision:
    """Require complete eight-set evidence and both strict gates on five sets."""
    if dataset_count != 8 or minimum_sets < 5 or minimum_sets > dataset_count:
        raise ValueError("MX gate requires dataset_count=8 and minimum_sets from 5 through 8")
    names = {item.dataset for item in reports}
    if len(names) != dataset_count:
        raise ValueError("dataset_count does not match MT5 dataset identities")
    candidates: list[tuple[float, str, int, int]] = []
    for variant in sorted({item.variant for item in reports}):
        evidence = [item for item in reports if item.variant == variant]
        if len(evidence) != dataset_count or len({item.dataset for item in evidence}) != dataset_count:
            continue
        qualified = [
            item
            for item in evidence
            if item.expectancy_ci_low > 0
            and item.mean_net_return_pct > item.random_p90_return_pct
            and not item.insufficient
        ]
        positive = sum(item.expectancy_ci_low > 0 for item in evidence)
        random_gate = sum(item.mean_net_return_pct > item.random_p90_return_pct for item in evidence)
        if len(qualified) >= minimum_sets:
            best = max(evidence, key=lambda item: (item.expectancy_ci_low, item.mean_expectancy_r))
            candidates.append((best.expectancy_ci_low, variant, positive, random_gate))
    if not candidates:
        return MT5Decision(
            None,
            "NO PROVEN EDGE ON MT5 DATA",
            (
                f"No WX variant passed CI and random-entry gates on at least "
                f"{minimum_sets}/8 datasets."
            ),
            dataset_count,
            0,
            0,
        )
    _ci_low, variant, positive, random_gate = max(candidates, key=lambda item: (item[0], item[1]))
    return MT5Decision(variant, "PROVEN EDGE", f"{variant} passed CI and random-entry gates on at least {minimum_sets}/8 datasets.", dataset_count, positive, random_gate)


def decide_mt5_hypothesis(
    results: Sequence[HypothesisResult], dataset_count: int = 8, minimum_sets: int = 5
) -> MT5Decision:
    """Apply same MX gate to H/exit combinations."""
    if dataset_count != 8 or minimum_sets < 5 or minimum_sets > dataset_count:
        raise ValueError("MX gate requires dataset_count=8 and minimum_sets from 5 through 8")
    names = {item.dataset for item in results}
    if len(names) != dataset_count:
        raise ValueError("dataset_count does not match MT5 dataset identities")
    candidates: list[tuple[float, str, int, int]] = []
    for key in sorted({item.key for item in results}):
        evidence = [item for item in results if item.key == key]
        if len(evidence) != dataset_count or len({item.dataset for item in evidence}) != dataset_count:
            continue
        qualified = [
            item
            for item in evidence
            if item.ci_low > 0
            and item.mean_net_return_pct > item.random_p90_return_pct
            and not item.insufficient
        ]
        positive = sum(item.ci_low > 0 for item in evidence)
        random_gate = sum(item.mean_net_return_pct > item.random_p90_return_pct for item in evidence)
        if len(qualified) >= minimum_sets:
            best = max(evidence, key=lambda item: (item.ci_low, item.expectancy_r))
            candidates.append((best.ci_low, key, positive, random_gate))
    if not candidates:
        return MT5Decision(
            None,
            "NO PROVEN EDGE ON MT5 DATA",
            (
                f"No YZ combination passed CI and random-entry gates on at least "
                f"{minimum_sets}/8 datasets."
            ),
            dataset_count,
            0,
            0,
        )
    _ci_low, key, positive, random_gate = max(candidates, key=lambda item: (item[0], item[1]))
    return MT5Decision(key, "PROVEN EDGE", f"{key} passed CI and random-entry gates on at least {minimum_sets}/8 datasets.", dataset_count, positive, random_gate)
