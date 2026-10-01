"""CSV journal for paper trades."""
from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path

JOURNAL_COLUMNS = ("timestamp", "symbol", "side", "entry", "exit", "sl", "tp", "qty", "pnl", "reason")


class TradeJournal:
    """Append paper-trade records to a stable CSV file."""

    def __init__(self, path: str | Path = "trades/journal.csv") -> None:
        self.path = Path(path)

    def append(self, trade: Mapping[str, object]) -> None:
        """Append one row, creating parent directories and header when needed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOURNAL_COLUMNS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow({column: trade.get(column, "") for column in JOURNAL_COLUMNS})
