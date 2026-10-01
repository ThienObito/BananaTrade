"""Run entry ablation on downloaded public Binance history."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.data.history import validate_klines
from bananatrade.data.indicators import atr
from bananatrade.research.entry_ablation import Dataset, run_research, write_reports
from bananatrade.research.hypothesis_research import (
    run_hypothesis_research,
    write_hypothesis_reports,
)

DATASETS = (("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "15m"), ("ETHUSDT", "1h"))


def load_dataset(symbol: str, interval: str) -> Dataset:
    path = Path("data/history") / f"{symbol}_{interval}.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            {
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "close_time": int(row["close_time"]),
            }
            for row in csv.DictReader(handle)
        ]
    validation = validate_klines(rows, interval)
    if not rows or validation.gaps or validation.duplicates or validation.invalid_rows:
        raise ValueError(f"history validation failed for {symbol}_{interval}: {validation}")
    frame = pd.DataFrame(rows)
    atr_values = atr(frame, 14)
    fallback_atr = (frame["high"] - frame["low"]).clip(lower=0.0000001)
    atr_values = atr_values.fillna(fallback_atr)
    enriched = [dict(row, atr14=float(value)) for row, value in zip(rows, atr_values)]
    return Dataset(symbol, interval, tuple(enriched), validation.gap_count, validation.duplicates, validation.invalid_rows)


def main() -> None:
    datasets = tuple(load_dataset(symbol, interval) for symbol, interval in DATASETS)
    engine = BacktestEngine()
    report = run_research(datasets, engine=engine, windows=5, random_runs=200, random_seed=510)
    hypothesis_report = run_hypothesis_research(datasets, engine=engine, random_runs=200, random_seed=510)
    Path("reports").mkdir(parents=True, exist_ok=True)
    write_reports(report, "reports/entry_research.md", "reports/entry_research.csv")
    write_hypothesis_reports(hypothesis_report, "reports/entry_hypotheses.md", "reports/entry_hypotheses.csv")
    coverage = {
        dataset.name: {
            "rows": len(dataset.candles),
            "gaps": dataset.gaps,
            "duplicates": dataset.duplicates,
            "invalid_rows": dataset.invalid_rows,
            "start_timestamp": dataset.candles[0]["timestamp"],
            "end_timestamp": dataset.candles[-1]["timestamp"],
        }
        for dataset in datasets
    }
    Path("reports/entry_coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    decision = asdict(report.decision)
    decision["gate_evidence"] = [asdict(item) for item in report.decision.gate_evidence]
    final = {
        "decision": decision,
        "hypothesis_decision": {
            "selected_variant": hypothesis_report.decision.selected_variant,
            "status": hypothesis_report.decision.status,
            "reason": hypothesis_report.decision.reason,
        },
        "hypothesis_combinations_tried": hypothesis_report.combinations_tried,
        "hypothesis_report": "reports/entry_hypotheses.md",
        "dataset_count": len(datasets),
        "dataset_names": [dataset.name for dataset in datasets],
        "window_count": report.window_count,
        "random_runs": report.random_runs,
        "random_seed": report.random_seed,
        "fee_rate": engine.fee_rate,
        "slippage_pct": engine.slippage_pct,
        "limit_expiry_bars": engine.limit_expiry_bars,
        "coverage_file": "reports/entry_coverage.json",
        "benchmark_note": "Decision gate uses random 90th percentile; buy-and-hold is informational.",
    }
    Path("reports/entry_decision.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(f"reports written; decision={report.decision.status}; selected={report.decision.selected_variant}")


if __name__ == "__main__":
    main()
