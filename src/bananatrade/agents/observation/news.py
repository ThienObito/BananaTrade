from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from bananatrade.agents.base import Agent
from bananatrade.agents.contexts import ObservationContext
from bananatrade.agents.schemas import ObservationReport


class NewsSource(Protocol):
    def fetch(self, symbol: str) -> list[str]: ...


class NullNewsSource:
    def fetch(self, symbol: str) -> list[str]:
        return []


class NewsAgent(Agent[ObservationContext, ObservationReport]):
    def __init__(self, gateway: object, source: NewsSource | None = None, prompt_file: Path | None = None) -> None:
        super().__init__("news", "tier1_fast", prompt_file or Path("prompts/market_scanner.v1.md"), ObservationReport, gateway)
        self.source = source or NullNewsSource()

    async def run(self, context: ObservationContext) -> ObservationReport:
        if not self.source.fetch(""):
            return ObservationReport(agent=self.name, symbol="", as_of=datetime.now(UTC), signals=[], confidence=0.0, data_missing=["news"], summary="No news source data.")
        return await super().run(context)
