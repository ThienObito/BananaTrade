"""Fetch up to 24 months of MT5 DEMO history for research only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bananatrade.brokers.mt5_client import MT5Client, MT5ConnectionError, MT5Unavailable
from bananatrade.research.mt5_history import (
    MT5_SYMBOLS,
    MT5_TIMEFRAMES,
    fetch_history,
    write_history_set,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--output", default="data/history")
    args = parser.parse_args()
    client = MT5Client(cache_dir=args.output)
    try:
        client.connect()
        sets = fetch_history(client, symbols=MT5_SYMBOLS, timeframes=MT5_TIMEFRAMES, days=args.days)
        points = {dataset.symbol: client.symbol_spec(dataset.symbol).point for dataset in sets}
    except (MT5Unavailable, MT5ConnectionError) as exc:
        print(f'MT5 terminal not connected: {exc}')
        return 2
    finally:
        client.shutdown()
    coverage = []
    for dataset in sets:
        output_path = write_history_set(dataset, args.output)
        validation = dataset.validation
        if not validation.valid:
            print(f"MT5 history validation failed: {dataset.name}: {validation}")
            return 3
        coverage.append({
            "dataset": dataset.name,
            "requested_symbol": dataset.requested_symbol,
            "resolved_symbol": dataset.symbol,
            "timeframe": dataset.timeframe,
            "path": output_path.name,
            "point": points[dataset.symbol],
            **validation.__dict__,
        })
        print(json.dumps(coverage[-1], separators=(",", ":")))
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / "mt5_coverage.json.tmp"
    temporary.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_root / "mt5_coverage.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
