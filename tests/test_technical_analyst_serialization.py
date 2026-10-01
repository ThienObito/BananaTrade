import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from bananatrade.agents.analysis.technical_analyst import TechnicalAnalyst, to_jsonable
from bananatrade.agents.contexts import AnalysisContext
from bananatrade.agents.schemas import ObservationReport, Signal
from bananatrade.data.triggers import Trigger

VALID_REPORT: dict[str, object] = {
    "agent": "technical_analyst",
    "symbol": "BTC/USDT",
    "as_of": "2025-01-01T00:00:00Z",
    "bias": "NEUTRAL",
    "thesis": "no directional edge",
    "key_levels": {"support": [95], "resistance": [105]},
    "invalidation": None,
    "confidence": 0.5,
    "evidence": [],
    "data_missing": [],
}


def test_report_containing_trigger_serializes_in_prompt() -> None:
    gateway = Mock()
    gateway.call = AsyncMock(return_value={"text": json.dumps(VALID_REPORT)})
    trigger = Trigger("range_breakout", "BTC/USDT", "1h", 105.0, 100.0, "up")

    asyncio.run(TechnicalAnalyst(gateway).run(AnalysisContext({}, [trigger], [])))

    prompt = gateway.call.await_args.args[1]
    assert '"name":"range_breakout"' in prompt
    assert '"direction":"up"' in prompt
    json.loads(
        prompt.split("SNAPSHOT AND TRIGGERS:\n", 1)[1].split("\nOBSERVATION REPORTS:\n", 1)[0]
    )


def test_pydantic_submodel_and_nested_datetime_serialize_in_prompt() -> None:
    gateway = Mock()
    gateway.call = AsyncMock(return_value={"text": json.dumps(VALID_REPORT)})
    as_of = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    observation = ObservationReport(
        agent="market_scanner",
        symbol="BTC/USDT",
        as_of=as_of,
        signals=[Signal(name="trend", direction="neutral", strength=0.4, evidence=[])],
        confidence=0.4,
        data_missing=[],
        summary="no clear trend",
    )

    asyncio.run(TechnicalAnalyst(gateway).run(AnalysisContext({}, [], [observation])))

    prompt = gateway.call.await_args.args[1]
    assert '"agent":"market_scanner"' in prompt
    assert '"as_of":"2025-01-02T03:04:05+00:00"' in prompt
    reports_text = prompt.split("OBSERVATION REPORTS:\n", 1)[1]
    assert json.loads(reports_text)[0]["signals"][0]["name"] == "trend"


def test_to_jsonable_converts_nested_values_and_datetime_to_iso8601() -> None:
    value = {
        "items": [datetime(2025, 1, 3, tzinfo=UTC), {"date": datetime(2025, 1, 4, tzinfo=UTC)}]
    }

    converted = to_jsonable(value)

    assert converted == {
        "items": ["2025-01-03T00:00:00+00:00", {"date": "2025-01-04T00:00:00+00:00"}]
    }
    assert json.dumps(converted) == (
        '{"items": ["2025-01-03T00:00:00+00:00", {"date": "2025-01-04T00:00:00+00:00"}]}'
    )
