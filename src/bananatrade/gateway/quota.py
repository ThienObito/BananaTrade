import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .errors import GatewayError


class QuotaExhaustedError(GatewayError):
    pass


class QuotaLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS calls (tier TEXT, ts TEXT, tokens INTEGER, status TEXT DEFAULT 'success')")
            try:
                connection.execute("ALTER TABLE calls ADD COLUMN status TEXT DEFAULT 'success'")
            except sqlite3.OperationalError:
                pass

    def check(self, tier: str, limits: dict[str, int]) -> None:
        now = datetime.now(UTC)
        with sqlite3.connect(self.path) as connection:
            for hours, key in [(5, "max_calls_per_5h"), (168, "max_calls_per_7d")]:
                since = (now - timedelta(hours=hours)).isoformat()
                count = connection.execute("SELECT COUNT(*) FROM calls WHERE tier=? AND ts>=? AND status='success'", (tier, since)).fetchone()[0]
                if count >= limits[key]:
                    raise QuotaExhaustedError(f"Quota exhausted for {tier}")

    def record(self, tier: str, tokens: int, status: str = "success") -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO calls (tier, ts, tokens, status) VALUES (?,?,?,?)", (tier, datetime.now(UTC).isoformat(), tokens, status))

    def counts(self, tier: str) -> tuple[int, int]:
        now = datetime.now(UTC)
        with sqlite3.connect(self.path) as connection:
            result = []
            for hours in (5, 168):
                since = (now - timedelta(hours=hours)).isoformat()
                result.append(connection.execute("SELECT COUNT(*) FROM calls WHERE tier=? AND ts>=? AND status='success'", (tier, since)).fetchone()[0])
        return result[0], result[1]
