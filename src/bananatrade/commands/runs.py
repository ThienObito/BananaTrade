import os
import sqlite3
from pathlib import Path

import typer

runs_app = typer.Typer(help="Inspect persisted pipeline runs.")
ROOT = Path(__file__).resolve().parents[3]


def _db_path() -> Path:
    return Path(os.getenv("BANANATRADE_DB_PATH", str(ROOT / "data" / "bananatrade.db")))


@runs_app.command("show")
def show(run_id: str) -> None:
    """Show every agent output row belonging to RUN_ID."""
    columns = ("agent", "status", "model_actual", "prompt_version", "error")
    with sqlite3.connect(_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT agent, status, model_actual, prompt_version, error "
                "FROM agent_outputs WHERE run_id = ? ORDER BY created_at, rowid",
                (run_id,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                rows = []
            else:
                raise
    if not rows:
        typer.echo(f"Unknown run_id: {run_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(" | ".join(columns))
    for row in rows:
        typer.echo(" | ".join(str(row[column] or "") for column in columns))


@runs_app.command("list")
def list_runs(limit: int = typer.Option(20, "--limit", min=1)) -> None:
    """List recent run IDs, newest first, with row counts and statuses."""
    with sqlite3.connect(_db_path()) as connection:
        try:
            rows = connection.execute(
                "SELECT run_id, COUNT(*) AS row_count, "
                "GROUP_CONCAT(DISTINCT status) AS statuses, MAX(created_at) AS newest "
                "FROM agent_outputs GROUP BY run_id ORDER BY newest DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                rows = []
            else:
                raise
    typer.echo("run_id | rows | statuses")
    for run_id, row_count, statuses, _newest in rows:
        typer.echo(f"{run_id} | {row_count} | {statuses or ''}")
