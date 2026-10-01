import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS agent_outputs (run_id TEXT, agent TEXT, tier TEXT, model_actual TEXT, prompt_version TEXT, symbol TEXT, as_of TEXT, output_json TEXT, status TEXT, error TEXT, tokens INTEGER, cost REAL, created_at TEXT)")


def save_runtime_result(path: Path, result: dict[str, Any]) -> None:
    initialize(path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS runtime_results (run_id TEXT PRIMARY KEY, symbol TEXT, as_of TEXT, result_json TEXT, created_at TEXT)")
        connection.execute("INSERT OR REPLACE INTO runtime_results VALUES (?, ?, ?, ?, ?)", (result["run_id"], result["symbol"], result["as_of"], json.dumps(result), datetime.now(UTC).isoformat()))


def save_agent_output(path: Path, *, run_id: str, agent: Any, result: Any, status: str, error: str | None = None, gateway_result: dict[str, Any] | None = None) -> None:
    initialize(path)
    report = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    gateway_result = gateway_result or {}
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO agent_outputs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, agent.name, agent.tier, gateway_result.get("actual_model"), agent.prompt_version,
             report.get("symbol", "") if isinstance(report, dict) else "", report.get("as_of", "") if isinstance(report, dict) else "",
             json.dumps(report), status, error, gateway_result.get("tokens"), gateway_result.get("cost"), datetime.now(UTC).isoformat()),
        )
