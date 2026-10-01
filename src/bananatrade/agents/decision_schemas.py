"""Schemas for the debate and final trading decision stages."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .schemas import Evidence


def no_numbers(value: str) -> str:
    """Reject prose containing numeric characters."""
    if re.search(r"\d", value):
        raise ValueError("must not contain numbers")
    return value


class DebateTurn(BaseModel):
    side: Literal["bull", "bear"]
    round: int = Field(ge=1)
    argument: str
    rebuts: str
    evidence: list[Evidence]

    _argument_no_numbers = field_validator("argument", "rebuts")(no_numbers)


class TradeProposal(BaseModel):
    symbol: str
    side: Literal["LONG", "SHORT", "HOLD"]
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    size_pct: float = Field(gt=0)
    timeframe: str
    thesis: str
    invalidation_condition: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]

    _prose_no_numbers = field_validator("thesis", "invalidation_condition")(no_numbers)

    def model_post_init(self, __context: object) -> None:
        if self.side == "HOLD" and any(v is not None for v in (self.entry, self.stop_loss, self.take_profit)):
            raise ValueError("HOLD proposals must not contain prices")
        if self.side != "HOLD" and any(v is None for v in (self.entry, self.stop_loss, self.take_profit)):
            raise ValueError("non-HOLD proposals require all prices")


class RiskView(BaseModel):
    stance: Literal["aggressive", "neutral", "conservative"]
    concerns: list[str]
    max_size_pct: float = Field(gt=0)


class Decision(BaseModel):
    action: Literal["APPROVE", "REJECT", "RESIZE"]
    final_size_pct: float = Field(ge=0)
    rationale: str
    key_risks: list[str]

    _rationale_no_numbers = field_validator("rationale")(no_numbers)
