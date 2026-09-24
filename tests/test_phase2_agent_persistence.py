import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from pydantic import BaseModel

from bananatrade.agents.base import Agent
from bananatrade.agents.observation.market_scanner import MarketScanner
from bananatrade.agents.schemas import ObservationReport
from bananatrade.storage.db import initialize, save_agent_output


def test_agent_run_stores_prompt_version(tmp_path: Path) -> None:
    prompt = tmp_path / "technical_analyst.v1.md"
    prompt.write_text("Return JSON.", encoding="utf-8")
    gateway = Mock()
    gateway.call = AsyncMock(return_value={"text": '{"value": 1}'})

    class Output(BaseModel):
        value: int

    agent = Agent("technical", "tier2_analyst", prompt, Output, gateway)
    result = asyncio.run(agent.run("context"))
    assert result.value == 1
    assert agent.prompt_version == "technical_analyst.v1"


def test_agent_outputs_persisted(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    initialize(path)
    columns = {row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(agent_outputs)")}
    assert columns == {"run_id", "agent", "tier", "model_actual", "prompt_version", "symbol", "as_of", "output_json", "status", "error", "tokens", "cost", "created_at"}


def test_persistence_success_failed_rejected(tmp_path: Path) -> None:
    path = tmp_path / "outputs.sqlite"
    initialize(path)
    agent = MarketScanner(object())
    report = ObservationReport(agent="market_scanner", symbol="BTC/USDT", as_of=datetime.now(UTC), signals=[], confidence=0.5, data_missing=[], summary="clear")
    save_agent_output(path, run_id="success", agent=agent, result=report, status="success", gateway_result={"actual_model": "gpt", "tokens": 10, "cost": 0.1})
    save_agent_output(path, run_id="failed", agent=agent, result=report, status="failed", error="gateway down")
    save_agent_output(path, run_id="rejected", agent=agent, result=report, status="rejected", error="Evidence mismatch")
    rows = sqlite3.connect(path).execute("SELECT run_id, status, error, prompt_version, model_actual, tokens FROM agent_outputs ORDER BY rowid").fetchall()
    assert [row[1] for row in rows] == ["success", "failed", "rejected"]
    assert rows[1][2] and rows[2][2]
    assert all(row[3] == "market_scanner.v2" for row in rows)
    assert rows[0][4] is not None and rows[0][5] is not None
