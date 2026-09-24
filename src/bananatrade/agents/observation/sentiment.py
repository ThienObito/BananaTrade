from pathlib import Path

from bananatrade.agents.base import Agent
from bananatrade.agents.contexts import ObservationContext
from bananatrade.agents.schemas import ObservationReport


class SentimentAgent(Agent[ObservationContext, ObservationReport]):
    def __init__(self, gateway: object, prompt_file: Path | None = None) -> None:
        super().__init__("sentiment", "tier1_fast", prompt_file or Path("prompts/sentiment.v2.md"), ObservationReport, gateway)
