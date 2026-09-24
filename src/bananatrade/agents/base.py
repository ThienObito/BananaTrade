import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bananatrade.gateway.structured import parse_structured


class Agent[ContextT, ReportT: BaseModel]:
    def __init__(self, name: str, tier: str, prompt_file: Path, output_schema: type[ReportT], gateway: Any) -> None:
        self.name = name
        self.tier = tier
        self.prompt_file = prompt_file
        self.output_schema = output_schema
        self.gateway = gateway
        self.last_gateway_result: dict[str, Any] = {}

    @property
    def prompt_version(self) -> str:
        return self.prompt_file.stem

    async def run(self, context: ContextT) -> ReportT:
        context_text = json.dumps(context.__dict__ if hasattr(context, "__dict__") else context, separators=(",", ":"), default=str)
        prompt = self.prompt_file.read_text(encoding="utf-8") + "\nSNAPSHOT AND TRIGGERS:\n" + context_text
        result = await self.gateway.call(self.tier, prompt)
        self.last_gateway_result = result
        return parse_structured(result["text"], self.output_schema)
