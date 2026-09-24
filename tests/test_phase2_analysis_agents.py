import asyncio
import json
from unittest.mock import AsyncMock, Mock

from bananatrade.agents.analysis.narrative_macro import NarrativeMacroAnalyst
from bananatrade.agents.analysis.technical_analyst import TechnicalAnalyst
from bananatrade.agents.contexts import AnalysisContext

VALID = {"agent": "technical_analyst", "symbol": "BTC/USDT", "as_of": "2025-01-01T00:00:00Z", "bias": "LONG", "thesis": "trend aligned", "key_levels": {"support": [95], "resistance": [105]}, "invalidation": {"level": 95, "condition": "below support"}, "confidence": 0.7, "evidence": [{"field": "timeframes.1h.last_price", "value": 95}], "data_missing": []}


def test_narrative_macro_zero_calls() -> None:
    gateway = Mock(); gateway.call = AsyncMock()
    report = asyncio.run(NarrativeMacroAnalyst(gateway).run(AnalysisContext({"symbol": "BTC/USDT"}, [], [])))
    assert report.data_missing == ["macro", "news"]
    gateway.call.assert_not_called()


def test_analyst_prompt_contains_observation_reports() -> None:
    gateway = Mock(); gateway.call = AsyncMock(return_value={"text": json.dumps(VALID)})
    report = Mock(); report.model_dump.return_value = {"agent": "market_scanner", "summary": "ok"}
    asyncio.run(TechnicalAnalyst(gateway).run(AnalysisContext({}, [], [report])))
    assert "OBSERVATION REPORTS:" in gateway.call.await_args.args[1]
    assert "market_scanner" in gateway.call.await_args.args[1]


def test_technical_analyst_invented_level_rejected() -> None:
    from bananatrade.agents.validator import EvidenceMismatchError, validate_report
    bad = dict(VALID)
    bad["key_levels"] = {"support": [94], "resistance": [105]}
    gateway = Mock(); gateway.call = AsyncMock(return_value={"text": json.dumps(bad)})
    result = asyncio.run(TechnicalAnalyst(gateway).run(AnalysisContext({}, [], [])))
    try:
        validate_report(result, {"timeframes": {"1h": {"last_price": 100}}})
    except EvidenceMismatchError as exc:
        assert "support" in str(exc)
    else:
        raise AssertionError("invented level accepted")


def test_technical_analyst_valid_report() -> None:
    gateway = Mock(); gateway.call = AsyncMock(return_value={"text": json.dumps(VALID)})
    agent = TechnicalAnalyst(gateway)
    result = asyncio.run(agent.run(AnalysisContext({}, [], [])))
    assert result.bias == "LONG"
    assert agent.prompt_version == "technical_analyst.v1"
