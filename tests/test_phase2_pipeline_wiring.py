import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from bananatrade.agents.analysis.technical_analyst import TechnicalAnalyst
from bananatrade.agents.observation.market_scanner import MarketScanner
from bananatrade.agents.observation.sentiment import SentimentAgent
from bananatrade.gateway.errors import ModelNotAvailableError
from bananatrade.orchestration.pipeline import run_agents

SNAPSHOT = {"symbol":"BTC/USDT","timeframes":{"1h":{"last_price":100,"indicators":{"rsi":55}},"4h":{"last_price":101,"indicators":{"rsi":52}}}}
OBS = lambda name: f'{"{\"agent\":\""}{name}{"\",\"symbol\":\"BTC/USDT\",\"as_of\":\"2025-01-01T00:00:00Z\",\"signals\":[],\"confidence\":0.5,\"data_missing\":[],\"summary\":\"neutral\"}"}'
ANALYSIS = '{"agent":"technical_analyst","symbol":"BTC/USDT","as_of":"2025-01-01T00:00:00Z","bias":"NEUTRAL","thesis":"neutral","key_levels":{"support":[],"resistance":[]},"invalidation":null,"confidence":0.5,"evidence":[],"data_missing":[]}'


def test_pipeline_observation_then_analysis(tmp_path: Path) -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[{"text": OBS("market_scanner"),"actual_model":"m","tokens":1},{"text": OBS("sentiment"),"actual_model":"m","tokens":1},{"text": ANALYSIS,"actual_model":"m","tokens":1}])
    asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path/"x.db", analysis_agents=[TechnicalAnalyst(gateway)]))
    assert "market_scanner" in gateway.call.await_args_list[2].args[1] and "sentiment" in gateway.call.await_args_list[2].args[1]
    assert sqlite3.connect(tmp_path/"x.db").execute("SELECT COUNT(*) FROM agent_outputs WHERE status='success'").fetchone()[0] == 3


def test_rejected_observation_not_passed_to_analyst(tmp_path: Path) -> None:
    bad = OBS("market_scanner").replace('"signals":[]', '"signals":[{"name":"x","direction":"neutral","strength":0.5,"evidence":[{"field":"timeframes.1h.indicators.rsi","value":999}]}]')
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[{"text":bad},{"text":OBS("sentiment")},{"text":ANALYSIS}])
    asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path/"x.db", analysis_agents=[TechnicalAnalyst(gateway)]))
    prompt = gateway.call.await_args_list[2].args[1]
    assert "market_scanner" not in prompt and "sentiment" in prompt


def test_all_observation_failed_analyst_still_runs(tmp_path: Path) -> None:
    gateway = Mock(); gateway.call = AsyncMock(side_effect=[ModelNotAvailableError("x"), ModelNotAvailableError("y"), {"text":ANALYSIS}])
    asyncio.run(run_agents([MarketScanner(gateway), SentimentAgent(gateway)], SNAPSHOT, db_path=tmp_path/"x.db", analysis_agents=[TechnicalAnalyst(gateway)]))
    assert "OBSERVATION REPORTS:" in gateway.call.await_args_list[2].args[1] and "[]" in gateway.call.await_args_list[2].args[1]


def test_single_run_id(tmp_path: Path) -> None:
    gateway = Mock(); gateway.call = AsyncMock(return_value={"text":OBS("market_scanner"),"actual_model":"m","tokens":1})
    db = tmp_path/"x.db"
    asyncio.run(run_agents([MarketScanner(gateway)], SNAPSHOT, db_path=db)); asyncio.run(run_agents([MarketScanner(gateway)], SNAPSHOT, db_path=db))
    ids = [row[0] for row in sqlite3.connect(db).execute("SELECT run_id FROM agent_outputs")]
    assert len(set(ids)) == 2
