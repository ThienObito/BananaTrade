"""Canonical, read-only market snapshot and agent runtime."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .agents.analysis.technical_analyst import TechnicalAnalyst
from .agents.observation.market_scanner import MarketScanner
from .agents.observation.sentiment import SentimentAgent
from .data.ccxt_source import CCXTPublicSource
from .data.snapshot import build_snapshot
from .data.triggers import evaluate_triggers
from .gateway.llm_client import LLMClient
from .orchestration.pipeline import run_agents
from .storage.db import save_runtime_result


class RuntimeService:
    """Fetch public Kraken data, run analysis agents, and persist an immutable result."""
    def __init__(self, root: Path, db_path: Path, gateway: Any | None = None) -> None:
        self.root, self.db_path = root, db_path
        self.config = dict(yaml.safe_load((root / "config" / "markets.yaml").read_text(encoding="utf-8")))
        self.gateway = gateway or LLMClient(root / "config" / "models.yaml", db_path)

    async def run(self, symbol: str) -> dict[str, Any]:
        source = CCXTPublicSource(self.config.get("exchange", "kraken"))
        try:
            frames = {tf: await source.ohlcv(symbol, tf, 300) for tf in self.config.get("timeframes", ["1h", "4h"])}
            orderbook = await source.orderbook(symbol)
            funding = await source.funding_rate(symbol)
        finally:
            await source.close()
        as_of = datetime.now(UTC)
        snapshot = build_snapshot(symbol, frames, orderbook, funding, as_of)
        triggers = evaluate_triggers(symbol, frames, funding, as_of, self.config.get("triggers", {}))
        reports = await run_agents(
            [MarketScanner(self.gateway), SentimentAgent(self.gateway)],
            snapshot.to_compact_dict(), db_path=self.db_path, triggers=triggers,
            analysis_agents=[TechnicalAnalyst(self.gateway)],
        )
        result = {"run_id": uuid4().hex, "symbol": symbol, "as_of": as_of.isoformat(),
                  "snapshot": snapshot.to_compact_dict(),
                  "triggers": [t.__dict__ if hasattr(t, "__dict__") else t for t in triggers],
                  "reports": [r.model_dump(mode="json") if hasattr(r, "model_dump") else r for r in reports],
                  "trading_enabled": False}
        save_runtime_result(self.db_path, result)
        return result


def run_sync(root: Path, db_path: Path, symbol: str) -> dict[str, Any]:
    return asyncio.run(RuntimeService(root, db_path).run(symbol))

