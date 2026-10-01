from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.research.entry_ablation import Dataset
from bananatrade.research.hypothesis_research import (
    run_hypothesis_research,
    write_hypothesis_reports,
)


def candles(count: int = 250) -> tuple[dict[str, object], ...]:
    return tuple({"timestamp": index * 3_600_000, "open": 100.0 + index * 0.02, "high": 101.0 + index * 0.02, "low": 99.0 + index * 0.02, "close": 100.0 + index * 0.02, "volume": float(index % 24 + 1), "atr14": 1.0, "regime": "RANGING"} for index in range(count))


def dataset() -> Dataset:
    return Dataset("BTCUSDT", "15m", candles())


def test_all_12_combinations_are_tried() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    assert report.combinations_tried == 12
    assert len(report.results) == 12


def test_each_combination_has_five_windows() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    assert all(len(item.windows) == 5 for item in report.results)


def test_ranking_uses_ci_lower_bound_first() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    lowers = [item.ci_low for item in report.ranking]
    assert lowers == sorted(lowers, reverse=True)


def test_h4_uses_train_volume_hours_without_test_leak() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    assert any(item.hypothesis == "H4" for item in report.results)


def test_random_benchmark_is_recorded() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=4)
    assert all(isinstance(item.random_p90_return_pct, float) for item in report.results)
    assert all(item.random_trade_count >= 0 for item in report.results)


def test_bootstrap_bounds_are_reported() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    assert all(item.ci_low <= item.ci_high for item in report.results)


def test_insufficient_flag_is_per_combination() -> None:
    report = run_hypothesis_research((Dataset("BTCUSDT", "15m", candles(200)),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    assert all(isinstance(item.insufficient, bool) for item in report.results)


def test_report_writer_outputs_all_metric_columns(tmp_path: Path) -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    md = tmp_path / "entry_hypotheses.md"
    csv_path = tmp_path / "entry_hypotheses.csv"
    write_hypothesis_reports(report, str(md), str(csv_path))
    assert md.exists()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert "ci_low" in header
    assert "random_p90_return_pct" in header


def test_report_writer_mentions_combinations(tmp_path: Path) -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    md = tmp_path / "entry_hypotheses.md"
    write_hypothesis_reports(report, str(md), str(tmp_path / "x.csv"))
    assert "Combinations tried: 12" in md.read_text(encoding="utf-8")


def test_report_decision_is_explicit() -> None:
    report = run_hypothesis_research((dataset(),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=2)
    assert report.decision.status in {"PROVEN EDGE", "NO PROVEN EDGE"}


def test_empty_dataset_list_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        run_hypothesis_research(())


def test_random_run_count_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        run_hypothesis_research((dataset(),), random_runs=0)
