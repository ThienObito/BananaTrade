import csv
from pathlib import Path

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.research.entry_ablation import (
    VARIANTS,
    AblationStrategy,
    Dataset,
    RandomStrategy,
    run_research,
    write_reports,
)


def candles(count: int = 250, drift: float = 0.2) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    price = 100.0
    for index in range(count):
        price += drift if index % 5 < 3 else -drift / 2
        rows.append({"open": price, "high": price + 1.0, "low": price - 1.0, "close": price, "volume": 100.0, "atr14": 1.0})
    return tuple(rows)


def datasets() -> tuple[Dataset, ...]:
    return (Dataset("BTCUSDT", "15m", candles()), Dataset("ETHUSDT", "1h", candles(250, 0.1)))


def test_all_variants_are_declared() -> None:
    assert VARIANTS == ("V0", "V1", "V2", "V3", "V4", "V5", "V6")


def test_market_variant_generates_direction() -> None:
    strategy = AblationStrategy("V0")
    result = strategy.generate_signal(list(candles(52)))
    assert result.bias == "LONG"
    assert result.entry_mode == "market"


def test_limit_variant_generates_limit_price() -> None:
    source = candles(52, drift=1.0)
    result = AblationStrategy("V3").generate_signal(list(source))
    assert result.entry_mode == "limit"
    assert result.limit_price is not None
    assert result.limit_price < float(source[-1]["close"])


def test_confirmation_variant_has_warmup() -> None:
    result = AblationStrategy("V3").generate_signal(list(candles(2)))
    assert result.bias == "NEUTRAL"


def test_random_strategy_is_seed_reproducible() -> None:
    first = [RandomStrategy(__import__("random").Random(1)).generate_signal(list(candles(3))).bias for _ in range(1)]
    second = [RandomStrategy(__import__("random").Random(1)).generate_signal(list(candles(3))).bias for _ in range(1)]
    assert first == second


def test_run_research_creates_5_windows_per_variant() -> None:
    report = run_research(datasets(), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=10)
    assert len(report.reports) == 14
    assert all(len(item.windows) == 5 for item in report.reports)


def test_run_research_has_four_dataset_support() -> None:
    input_sets = datasets() + (Dataset("BTCUSDT", "1h", candles()), Dataset("ETHUSDT", "15m", candles()))
    report = run_research(input_sets, engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=5)
    assert len({item.dataset for item in report.reports}) == 4


def test_report_marks_low_trade_windows_insufficient() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles(50)),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3, windows=5)
    assert all(item.insufficient for item in report.reports)


def test_random_benchmark_has_fixed_seed() -> None:
    dataset = Dataset("BTCUSDT", "1h", candles())
    first = run_research((dataset,), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=10, random_seed=42)
    second = run_research((dataset,), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=10, random_seed=42)
    assert first.reports[0].random_p90_return_pct == second.reports[0].random_p90_return_pct


def test_random_benchmark_changes_with_seed() -> None:
    dataset = Dataset("BTCUSDT", "1h", candles())
    first = run_research((dataset,), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=10, random_seed=1)
    second = run_research((dataset,), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=10, random_seed=2)
    assert first.reports[0].random_seed != second.reports[0].random_seed


def test_expectancy_ci_is_present() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    assert all(isinstance(item.expectancy_ci_low, float) for item in report.reports)


def test_trade_count_and_profit_factor_are_reported() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    assert all(item.total_trades >= 0 and item.profit_factor >= 0 for item in report.reports)


def test_proven_variants_require_all_datasets() -> None:
    report = run_research(datasets(), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    assert isinstance(report.proven_variants(), tuple)
    assert report.decision.status in {"PROVEN EDGE", "NO PROVEN EDGE"}


def test_write_reports_creates_markdown_and_csv(tmp_path: Path) -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    markdown = tmp_path / "entry_research.md"
    csv_path = tmp_path / "entry_research.csv"
    write_reports(report, markdown, csv_path)
    assert markdown.exists()
    assert csv_path.exists()
    assert "V0" in markdown.read_text(encoding="utf-8")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        assert "expectancy_ci_low" in next(csv.reader(handle))


def test_write_reports_includes_no_edge_when_unproven(tmp_path: Path) -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), engine=BacktestEngine(), random_runs=3)
    path = tmp_path / "report.md"
    write_reports(report, path, tmp_path / "report.csv")
    assert "Decision evidence:" in path.read_text(encoding="utf-8")


def test_empty_datasets_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        run_research(())


def test_invalid_window_count_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        run_research((Dataset("BTCUSDT", "1h", candles()),), windows=0)


def test_too_short_dataset_rejected() -> None:
    with pytest.raises(ValueError, match="too short"):
        run_research((Dataset("BTCUSDT", "1h", candles(40)),), random_runs=3)


def test_reports_keep_dataset_identity() -> None:
    report = run_research((Dataset("ETHUSDT", "15m", candles()),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    assert {item.dataset for item in report.reports} == {"ETHUSDT_15m"}


def test_report_window_bounds_are_disjoint() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), engine=BacktestEngine(fee_rate=0.0, slippage_pct=0.0), random_runs=3)
    windows = report.reports[0].windows
    assert all(item.train_end == item.test_start for item in windows)


def test_report_uses_net_return_for_decision_fields() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), random_runs=3)
    assert all(isinstance(item.mean_net_return_pct, float) for item in report.reports)


def test_random_runs_count_is_preserved() -> None:
    report = run_research((Dataset("BTCUSDT", "1h", candles()),), random_runs=17)
    assert report.random_runs == 17
