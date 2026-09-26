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
        if not isinstance(tier, str) or not tier.strip():
            raise ValueError("Tier must be a non-empty string")
        if not isinstance(limits, dict):
            raise TypeError("Quota limits must be a dictionary")
        required = ("max_calls_per_5h", "max_calls_per_7d")
        missing = [key for key in required if key not in limits]
        if missing:
            raise ValueError(f"Missing quota limits: {', '.join(missing)}")
        if any(limits[key] < 0 for key in required):
            raise ValueError("Quota limits cannot be negative")
        now = datetime.now(UTC)
        with sqlite3.connect(self.path) as connection:
            for hours, key in [(5, "max_calls_per_5h"), (168, "max_calls_per_7d")]:
                since = (now - timedelta(hours=hours)).isoformat()
                count = connection.execute("SELECT COUNT(*) FROM calls WHERE tier=? AND ts>=? AND status='success'", (tier, since)).fetchone()[0]
                if count >= limits[key]:
                    raise QuotaExhaustedError(f"Quota exhausted for {tier}")

    def record(self, tier: str, tokens: int, status: str = "success") -> None:
        if not isinstance(tier, str) or not tier.strip():
            raise ValueError("Tier must be a non-empty string")
        if not isinstance(tokens, int) or isinstance(tokens, bool):
            raise TypeError("Token count must be an integer")
        if tokens < 0:
            raise ValueError("Token count cannot be negative")
        if status not in {"success", "failed"}:
            raise ValueError("Invalid ledger status")
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
