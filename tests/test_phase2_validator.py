from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bananatrade.agents.schemas import (
    AnalysisReport,
    Evidence,
    Invalidation,
    KeyLevels,
    Signal,
)
from bananatrade.agents.validator import EvidenceMismatchError, validate_report
from bananatrade.orchestration.pipeline import run_agents

SNAPSHOT = {"symbol": "BTC/USDT", "s": 95.0, "r": 105.0, "x": 50.0, "y": 150.0, "timeframes": {"1h": {"last_price": 100.0, "indicators": {"ema": 98.5}}}}


def report(evidence: list[Evidence], levels: KeyLevels | None = None) -> AnalysisReport:
    chosen = levels or KeyLevels(support=[95], resistance=[105])
    invalidation = Invalidation(level=chosen.support[0], condition="below support")
    values = list(evidence)
    for field, value in [("s", chosen.support[0]), ("r", chosen.resistance[0]), ("i", invalidation.level)]:
        if not any(item.value == value for item in values):
            values.append(Evidence(field=field, value=value))
    return AnalysisReport(agent="test", symbol="BTC/USDT", as_of=datetime.now(UTC), bias="LONG", thesis="ok", key_levels=chosen, invalidation=invalidation, confidence=0.8, evidence=values, data_missing=[])


def test_evidence_valid_passes() -> None:
    assert validate_report(report([Evidence(field="timeframes.1h.indicators.ema", value=98.5)]), SNAPSHOT)


def test_evidence_unknown_field_rejected() -> None:
    with pytest.raises(EvidenceMismatchError, match="timeframes.1h.indicators.macd"):
        validate_report(report([Evidence(field="timeframes.1h.indicators.macd", value=1)]), SNAPSHOT)

@pytest.mark.parametrize("value, valid", [(98.509, True), (98.6, False)])
def test_evidence_value_tolerance(value: float, valid: bool) -> None:
    if valid:
        validate_report(report([Evidence(field="timeframes.1h.indicators.ema", value=value)]), SNAPSHOT)
    else:
        with pytest.raises(EvidenceMismatchError, match="ema"):
            validate_report(report([Evidence(field="timeframes.1h.indicators.ema", value=value)]), SNAPSHOT)

@pytest.mark.parametrize("levels", [KeyLevels(support=[0], resistance=[100]), KeyLevels(support=[-1], resistance=[100]), KeyLevels(support=[1], resistance=[200])])
def test_key_levels_rejected(levels: KeyLevels) -> None:
    with pytest.raises(EvidenceMismatchError):
        validate_report(report([], levels), SNAPSHOT)


def test_key_level_exactly_fifty_percent_is_allowed() -> None:
    assert validate_report(report([Evidence(field="x", value=50), Evidence(field="y", value=150)], KeyLevels(support=[50], resistance=[150])), SNAPSHOT)


@pytest.mark.asyncio
async def test_pipeline_continues_after_evidence_mismatch() -> None:
    class Store:
        def __init__(self): self.rows = []
        def save(self, output, agent, status, error=None): self.rows.append((status, error))

    class Fake:
        def __init__(self, output): self.output = output; self.last_output = output
        async def run(self, context): return self.output

    good = report([Evidence(field="timeframes.1h.indicators.ema", value=98.5)])
    bad = report([Evidence(field="timeframes.1h.indicators.ema", value=1)])
    store = Store()
    result = await run_agents([Fake(bad), Fake(good)], SNAPSHOT, store)
    assert result == [good]
    assert [row[0] for row in store.rows] == ["rejected", "accepted"]

@pytest.mark.parametrize("field, value", [("confidence", -0.1), ("confidence", 1.1), ("strength", -0.1), ("strength", 1.1)])
def test_schema_bounds(field: str, value: float) -> None:
    if field == "confidence":
        with pytest.raises(ValidationError): report([], ).__class__.model_validate({**report([]).model_dump(), field: value})
    else:
        with pytest.raises(ValidationError): Signal(name="x", direction="bullish", strength=value, evidence=[])


def test_schema_text_and_enum_bounds() -> None:
    with pytest.raises(ValidationError): AnalysisReport.model_validate({**report([]).model_dump(), "thesis": "x" * 601})
    with pytest.raises(ValidationError): Signal(name="x", direction="invalid", strength=0.5, evidence=[])
    with pytest.raises(ValidationError): AnalysisReport(agent="x", symbol="x", as_of=datetime.now(UTC), bias="BAD", thesis="x", key_levels=KeyLevels(support=[], resistance=[]), invalidation=1, confidence=.5, evidence=[], data_missing=[])
