import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from bananatrade.agents.observation.market_scanner import MarketScanner
from bananatrade.agents.observation.sentiment import SentimentAgent
from bananatrade.gateway.errors import EmptyCompletionError, ModelNotAvailableError
from bananatrade.gateway.structured import StructuredOutputError
from bananatrade.orchestration.pipeline import run_agents

SNAPSHOT = {"symbol": "BTC/USDT", "as_of": "2025-01-01T00:00:00Z", "timeframes": {"1h": {"last_price": 100.0, "indicators": {"rsi": 55.0}}, "4h": {"last_price": 101.0, "indicators": {"rsi": 52.0}}}}


def text(agent: str, value: float = 55.0) -> str:
    return json.dumps({"agent": agent, "symbol": "BTC/USDT", "as_of": "2025-01-01T00:00:00Z", "signals": [{"name": "momentum", "direction": "neutral", "strength": 0.5, "evidence": [{"field": "timeframes.1h.indicators.rsi", "value": value}]}], "confidence": 0.6, "data_missing": [], "summary": "Momentum is neutral."})


def make_agents(side_effect):
    gateway = Mock()
    gateway.call = AsyncMock(side_effect=side_effect)
    return [MarketScanner(gateway), SentimentAgent(gateway)]


def rows(path: Path):
    return sqlite3.connect(path).execute("SELECT agent, status, error, prompt_version, model_actual, tokens FROM agent_outputs ORDER BY rowid").fetchall()


def test_pipeline_valid_reports_persisted(tmp_path: Path) -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[{"text": text("market_scanner"), "actual_model": "m", "tokens": 10, "cost": 0.1}, {"text": text("sentiment"), "actual_model": "m", "tokens": 11, "cost": 0.1}])
    result = asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path / "x.db"))
    assert len(result) == 2
    data = rows(tmp_path / "x.db")
    assert [row[1] for row in data] == ["success", "success"]
    assert [row[3] for row in data] == ["market_scanner.v2", "sentiment.v2"]
    assert all(row[4] is not None and row[5] is not None for row in data)

@pytest.mark.parametrize("bad", ["market_scanner", "sentiment"])
def test_pipeline_fabricated_number_rejected_and_persisted(tmp_path: Path, bad: str) -> None:
    values = [text("market_scanner", 999.0) if bad == "market_scanner" else text("market_scanner"), text("sentiment", 999.0) if bad == "sentiment" else text("sentiment")]
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[{"text": values[0], "actual_model": "m", "tokens": 10}, {"text": values[1], "actual_model": "m", "tokens": 10}])
    result = asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path / "x.db"))
    assert len(result) == 1
    data = rows(tmp_path / "x.db")
    assert "rejected" in [row[1] for row in data]
    assert any(row[2] and "Evidence mismatch" in row[2] for row in data)


def test_pipeline_gateway_error_failed_and_persisted(tmp_path: Path) -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[ModelNotAvailableError("bad model"), {"text": text("sentiment"), "actual_model": "m", "tokens": 10}])
    result = asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path / "x.db"))
    assert len(result) == 1
    data = rows(tmp_path / "x.db")
    assert data[0][1] == "failed" and "bad model" in data[0][2]

@pytest.mark.parametrize("error", [StructuredOutputError("bad json"), StructuredOutputError("schema violation"), EmptyCompletionError("empty")])
def test_pipeline_non_gateway_agent_errors(tmp_path: Path, error: Exception) -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[error, {"text": text("sentiment"), "actual_model": "m", "tokens": 10}])
    result = asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path / "x.db"))
    assert len(result) == 1
    assert rows(tmp_path / "x.db")[0][1] == "failed"


def test_unexpected_bug_is_not_swallowed() -> None:
    class BugAgent:
        name = "bug"
        tier = "tier1_fast"
        prompt_version = "bug.v1"
        async def run(self, snapshot):
            raise ValueError("programming bug")
    with pytest.raises(ValueError, match="programming bug"):
        asyncio.run(run_agents([BugAgent()], SNAPSHOT))


def test_news_null_source_zero_llm_calls(tmp_path: Path) -> None:
    from bananatrade.agents.observation.news import NewsAgent, NullNewsSource
    gateway = Mock(); gateway.call = AsyncMock()
    report = asyncio.run(NewsAgent(gateway, NullNewsSource()).run(SNAPSHOT))
    assert report.data_missing == ["news"]
    gateway.call.assert_not_called()


def test_prompts_contain_compact_snapshot_and_triggers() -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[{"text": text("market_scanner")}, {"text": text("sentiment")}])
    asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], {**SNAPSHOT, "triggers": ["funding_extreme" ]}))
    for call in gateway.call.await_args_list:
        prompt = call.args[1]
        assert "SNAPSHOT AND TRIGGERS:" in prompt
        assert "funding_extreme" in prompt
        assert "timestamp_ms" not in prompt
        assert len(prompt) < 10000
