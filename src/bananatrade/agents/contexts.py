from dataclasses import dataclass
from typing import Any

from bananatrade.agents.schemas import ObservationReport


@dataclass(frozen=True)
class ObservationContext:
    snapshot: dict[str, Any]
    triggers: list[Any]


@dataclass(frozen=True)
class AnalysisContext:
    snapshot: dict[str, Any]
    triggers: list[Any]
    observation_reports: list[ObservationReport]
