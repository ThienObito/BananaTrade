import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bananatrade.agents.base import Agent
from bananatrade.agents.contexts import AnalysisContext
from bananatrade.agents.schemas import AnalysisReport


def to_jsonable(value: Any) -> Any:
    if value.__class__.__module__ == "unittest.mock":
        dumper = getattr(value, "model_dump", None)
        if callable(dumper):
            dumped = dumper()
            if dumped.__class__.__module__ != "unittest.mock":
                return to_jsonable(dumped)
        return str(value)
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return to_jsonable(model_dump())
    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        return to_jsonable(as_dict())
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: to_jsonable(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }
    return value


class TechnicalAnalyst(Agent[AnalysisContext, AnalysisReport]):
    def __init__(self, gateway: Any, prompt_file: Path | None = None) -> None:
        super().__init__(
            "technical_analyst",
            "tier2_analyst",
            prompt_file or Path("prompts/technical_analyst.v1.md"),
            AnalysisReport,
            gateway,
        )

    async def run(self, context: AnalysisContext) -> AnalysisReport:
        triggers = [to_jsonable(item) for item in context.triggers]
        text = json.dumps(
            {"snapshot": to_jsonable(context.snapshot), "triggers": triggers}, separators=(",", ":")
        )
        text += "\nOBSERVATION REPORTS:\n" + json.dumps(
            to_jsonable(context.observation_reports), separators=(",", ":")
        )
        result = await self.gateway.call(
            self.tier,
            self.prompt_file.read_text(encoding="utf-8") + "\nSNAPSHOT AND TRIGGERS:\n" + text,
        )
        self.last_gateway_result = result
        from bananatrade.gateway.structured import parse_structured

        return parse_structured(result["text"], self.output_schema)
