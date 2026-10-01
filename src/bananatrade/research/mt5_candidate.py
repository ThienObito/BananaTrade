"""Persist MX candidate metadata only after research gate approval."""

from __future__ import annotations

import json
from pathlib import Path

from .mt5_decision import MT5Decision


def persist_candidate(decision: MT5Decision, path: str | Path) -> None:
    """Write selected research candidate or explicit no-edge state."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "candidate": decision.selected_variant,
        "status": decision.status,
        "reason": decision.reason,
        "dataset_count": decision.dataset_count,
        "positive_ci_datasets": decision.positive_ci_datasets,
        "random_gate_datasets": decision.random_gate_datasets,
        "execution_enabled": False,
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
