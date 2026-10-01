"""SQLite schema migrations for BananaTrade storage."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LATEST_VERSION = 1

_MIGRATIONS: dict[int, str] = {
    1: """
        CREATE TABLE IF NOT EXISTS agent_outputs (
            run_id TEXT, agent TEXT, tier TEXT, model_actual TEXT,
            prompt_version TEXT, symbol TEXT, as_of TEXT, output_json TEXT,
            status TEXT, error TEXT, tokens INTEGER, cost REAL, created_at TEXT
        )
    """,
}


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    if conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
        # Databases created by the pre-migration db.py already have migration 1.
        tables = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_outputs'"
        ).fetchone()
        conn.execute("INSERT INTO schema_version(version) VALUES (?)", (1 if tables else 0,))


def status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the installed schema version and ordered pending versions."""
    _ensure_version_table(conn)
    current = int(conn.execute("SELECT version FROM schema_version").fetchone()[0])
    return {"current": current, "pending": list(range(current + 1, LATEST_VERSION + 1))}


def apply_migrations(conn: sqlite3.Connection, db_path: Path) -> dict[str, Any]:
    """Back up *db_path* and apply all pending migrations transactionally."""
    info = status(conn)
    pending = info["pending"]
    if not pending:
        return info
    db_path = Path(db_path)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    backup_path = backup_dir / f"{timestamp}.db"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
    else:
        conn.commit()
        shutil.copy2(db_path, backup_path) if db_path.exists() else backup_path.touch()
    try:
        with conn:
            for version in pending:
                conn.executescript(_MIGRATIONS[version])
                conn.execute("UPDATE schema_version SET version = ?", (version,))
    except Exception:
        raise
    result = status(conn)
    result["backup"] = str(backup_path)
    return result
