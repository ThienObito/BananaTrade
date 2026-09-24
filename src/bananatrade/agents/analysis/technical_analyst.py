import json
from pathlib import Path
from typing import Any

from bananatrade.agents.base import Agent
from bananatrade.agents.contexts import AnalysisContext
from bananatrade.agents.schemas import AnalysisReport


class TechnicalAnalyst(Agent[AnalysisContext, AnalysisReport]):
    def __init__(self, gateway: Any, prompt_file: Path | None = None) -> None:
        super().__init__("technical_analyst", "tier2_analyst", prompt_file or Path("prompts/technical_analyst.v1.md"), AnalysisReport, gateway)

    async def run(self, context: AnalysisContext) -> AnalysisReport:
        text = json.dumps({"snapshot": context.snapshot, "triggers": context.triggers}, separators=(",", ":"))
        text += "\nOBSERVATION REPORTS:\n" + json.dumps([report.model_dump(mode="json") for report in context.observation_reports], separators=(",", ":"))
        result = await self.gateway.call(self.tier, self.prompt_file.read_text(encoding="utf-8") + "\nSNAPSHOT AND TRIGGERS:\n" + text)
        self.last_gateway_result = result
        from bananatrade.gateway.structured import parse_structured
        return parse_structured(result["text"], self.output_schema)
