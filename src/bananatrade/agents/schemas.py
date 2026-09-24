from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Invalidation(BaseModel):
    level: float
    condition: str = Field(max_length=200)


class Evidence(BaseModel):
    field: str
    value: float
class Signal(BaseModel):
    name: str
    direction: Literal["bullish", "bearish", "neutral"]
    strength: float = Field(ge=0, le=1)
    evidence: list[Evidence]
class ObservationReport(BaseModel):
    agent: str
    symbol: str
    as_of: datetime
    signals: list[Signal]
    confidence: float = Field(ge=0, le=1)
    data_missing: list[str]
    summary: str = Field(max_length=400)
class KeyLevels(BaseModel):
    support: list[float]
    resistance: list[float]
class AnalysisReport(BaseModel):
    agent: str
    symbol: str
    as_of: datetime
    bias: Literal["LONG", "SHORT", "NEUTRAL"]
    thesis: str = Field(max_length=600)
    key_levels: KeyLevels
    invalidation: Invalidation | None
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    data_missing: list[str]
