from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bananatrade.agents.base import Agent
from bananatrade.agents.contexts import AnalysisContext
from bananatrade.agents.schemas import AnalysisReport, KeyLevels


class NarrativeMacroAnalyst(Agent[AnalysisContext, AnalysisReport]):
    def __init__(self, gateway: Any) -> None:
        super().__init__("narrative_macro", "tier2_analyst", Path("prompts/technical_analyst.v1.md"), AnalysisReport, gateway)

    async def run(self, context: AnalysisContext) -> AnalysisReport:
        return AnalysisReport(agent=self.name, symbol=context.snapshot.get("symbol", ""), as_of=datetime.now(UTC), bias="NEUTRAL", thesis="Macro and news sources are unavailable.", key_levels=KeyLevels(support=[], resistance=[]), invalidation=None, confidence=0.0, evidence=[], data_missing=["macro", "news"])
