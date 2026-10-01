"""Run the observation -> technical-analysis pipeline for one symbol."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer

from ..agents.analysis.technical_analyst import TechnicalAnalyst
from ..agents.observation.market_scanner import MarketScanner
from ..agents.observation.sentiment import SentimentAgent
ROOT = Path(__file__).resolve().parents[3]
from ..data.snapshot import build_snapshot
from ..data.triggers import evaluate_triggers
from ..gateway.llm_client import LLMClient
from ..orchestration.pipeline import run_agents

analyze_app = typer.Typer(no_args_is_help=True)
_ALLOWED = {"tier1_fast", "tier2_analyst"}


class AllowedTiersGateway:
    """A defensive gateway wrapper: forbidden tiers fail before the real call."""

    def __init__(self, gateway: Any) -> None:
        self.gateway = gateway
        self.calls: list[dict[str, Any]] = []

    async def call(self, tier: str, prompt: str) -> dict[str, Any]:
        if tier not in _ALLOWED:
            raise ValueError(f"tier {tier} is not allowed for analyze")
        started = time.perf_counter()
        result = await self.gateway.call(tier, prompt)
        self.calls.append({"tier": tier, "prompt": prompt, "result": result, "latency": time.perf_counter() - started})
        return result


def _db_path() -> Path:
    return Path(os.getenv("BANANATRADE_DB_PATH", ROOT / "data" / "bananatrade.db"))


def _prompts(agents: list[Any]) -> None:
    for agent in agents:
        prompt = agent.prompt_file.read_text(encoding="utf-8")
        typer.echo(f"agent={agent.name} tier={agent.tier} model_id=? prompt_length={len(prompt)}")


def _transcript(path: Path, run_id: str, symbol: str, as_of: Any, triggers: list[Any], calls: list[dict[str, Any]]) -> bool:
    typer.echo(f"ANALYZE run_id={run_id} symbol={symbol} as_of={as_of.isoformat()} triggers={len(triggers)}")
    rows: list[tuple[Any, ...]] = []
    if path.exists():
        with sqlite3.connect(path) as db:
            rows = db.execute("SELECT agent,tier,model_actual,status,error,tokens,cost FROM agent_outputs ORDER BY rowid DESC LIMIT 20").fetchall()
    rows.reverse()
    succeeded = False
    for agent, tier, model, status, error, tokens, cost in rows:
        typer.echo(f"{agent} status={status} model_actual={model or '-'} tokens={tokens or 0} latency=- content={error or '-'}")
        succeeded = succeeded or (agent == "technical_analyst" and status == "success")
    total_tokens = sum(int(r[5] or 0) for r in rows)
    total_cost = sum(float(r[6] or 0) for r in rows)
    typer.echo(f"FOOTER calls={len(calls)} tokens={total_tokens} est_cost={total_cost:.6f} quota_before=? quota_after=?")
    return succeeded


@analyze_app.command("analyze")
def analyze(symbol: str, dry_run: bool = typer.Option(False, "--dry-run"), offline: bool = typer.Option(False, "--offline")) -> None:
    """Analyze SYMBOL using only tier1_fast and tier2_analyst."""
    try:
        from ..cli import _config, _load_symbol, _offline_as_of
        frames, orderbook, funding = asyncio.run(_load_symbol(symbol, offline))
        as_of = _offline_as_of(frames) if offline else __import__("pandas").Timestamp.now(tz="UTC")
        snapshot = build_snapshot(symbol, frames, orderbook, funding, as_of.to_pydatetime())
        triggers = evaluate_triggers(symbol, frames, funding, as_of.to_pydatetime(), _config().get("triggers", {}))
        agents = [MarketScanner(None), SentimentAgent(None), TechnicalAnalyst(None)]
        if dry_run:
            _prompts(agents)
            return
        gateway = AllowedTiersGateway(LLMClient(ROOT / "config" / "models.yaml", _db_path()))
        for agent in agents:
            agent.gateway = gateway
        run_id = uuid4().hex
        asyncio.run(run_agents(agents[:2], snapshot.to_compact_dict(), db_path=_db_path(), triggers=triggers, analysis_agents=[agents[2]]))
        ok = _transcript(_db_path(), run_id, symbol, snapshot.timestamp, triggers, gateway.calls)
        if not ok:
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"ERROR {symbol}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
