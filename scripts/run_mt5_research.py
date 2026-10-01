"""Run research-only MT5 historical analysis; never place orders."""

from __future__ import annotations

import argparse
from pathlib import Path

from bananatrade.config import Config
from bananatrade.research.mt5_candidate import persist_candidate
from bananatrade.research.mt5_decision import decide_mt5_entry, decide_mt5_hypothesis
from bananatrade.research.mt5_research import (
    load_coverage,
    load_mt5_datasets,
    run_mt5_research,
    write_mt5_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="data/history")
    parser.add_argument("--coverage", default="data/history/mt5_coverage.json")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--config", default=None)
    parser.add_argument("--commission-per-lot", type=float, default=None)
    parser.add_argument("--candidate", default="data/mt5_candidate.json")
    parser.add_argument("--decision", default="reports/mt5_decision.json")
    args = parser.parse_args()
    config = Config.load_from_file(args.config) if args.config else Config.load_from_env()
    if config.mt5_execution_enabled:
        raise SystemExit("MT5 research requires execution_enabled=false")
    commission = config.commission_per_lot if args.commission_per_lot is None else args.commission_per_lot
    coverage = load_coverage(args.coverage)
    datasets = load_mt5_datasets(args.history, coverage)
    points = {item.resolved_symbol: item.point for item in coverage}
    report = run_mt5_research(
        datasets,
        points,
        config=config,
        coverage=coverage,
        commission_per_lot=commission,
        random_runs=200,
    )
    output = Path(args.reports)
    write_mt5_reports(report, output / "mt5_research.md", output / "mt5_research.csv", commission)
    entry_decision = report.entry_decision or decide_mt5_entry(report.entry.reports)
    hypothesis_decision = report.hypothesis_decision or decide_mt5_hypothesis(report.hypothesis.results)
    selected_decision = entry_decision if entry_decision.selected_variant is not None else hypothesis_decision
    persist_candidate(selected_decision, args.candidate)
    decision_path = Path(args.decision)
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(
        __import__("json").dumps({
            "entry_decision": vars(entry_decision),
            "hypothesis_decision": vars(hypothesis_decision),
            "coverage": [vars(item) for item in report.coverage],
            "points": dict(report.points),
            "execution_enabled": False,
            "candidate_path": str(args.candidate),
            "reports_path": str(output),
        }, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"WX: {entry_decision.status}; YZ: {hypothesis_decision.status}; execution_enabled=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
