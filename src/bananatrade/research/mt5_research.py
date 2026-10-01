"""Research-only MT5 dataset loading, orchestration, and unified reports."""

from __future__ import annotations

import csv
import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import cast

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..config import Config
from ..data.indicators import atr
from .entry_ablation import BOOTSTRAP_RUNS, Dataset, ResearchReport, run_research
from .hypothesis_research import HypothesisResearchReport, run_hypothesis_research
from .mt5_costs import MT5CostModel
from .mt5_decision import MT5Decision, decide_mt5_entry, decide_mt5_hypothesis
from .mt5_history import MT5_SYMBOLS, MT5_TIMEFRAMES, validate_history


@dataclass(frozen=True)
class MT5Coverage:
    requested_symbol: str
    resolved_symbol: str
    timeframe: str
    path: str
    point: float
    rows: int
    start: str | None
    end: str | None
    gaps: int
    duplicates: int
    invalid_rows: int


@dataclass(frozen=True)
class MT5ResearchReport:
    entry: ResearchReport
    hypothesis: HypothesisResearchReport
    datasets: tuple[Dataset, ...]
    coverage: tuple[MT5Coverage, ...]
    points: Mapping[str, float]
    entry_decision: MT5Decision | None = None
    hypothesis_decision: MT5Decision | None = None


def load_mt5_dataset(
    path: str | Path,
    requested_symbol: str,
    resolved_symbol: str,
    timeframe: str,
) -> Dataset:
    """Load one validated MT5 CSV, preserving spread points."""
    if timeframe not in MT5_TIMEFRAMES:
        raise ValueError(f"unsupported MT5 timeframe: {timeframe}")
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"MT5 history file not found: {source}")
    with source.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, object]] = []
        for raw in csv.DictReader(handle):
            required = ("timestamp", "open", "high", "low", "close", "spread")
            if any(field not in raw or raw[field] in {None, ""} for field in required):
                raise ValueError(f"MT5 CSV missing required field in {source}")
            timestamp = int(float(raw["timestamp"]))
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            volume_raw = raw.get("tick_volume") or raw.get("real_volume") or raw.get("volume")
            if volume_raw in {None, ""}:
                raise ValueError(f"MT5 CSV missing volume in {source}")
            rows.append({
                "timestamp": timestamp,
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "spread": float(raw["spread"]),
                "volume": float(volume_raw),
                "tick_volume": float(raw.get("tick_volume") or 0.0),
                "real_volume": float(raw.get("real_volume") or 0.0),
            })
    validation = validate_history(rows, MT5_TIMEFRAMES[timeframe])
    if not validation.valid:
        raise ValueError(f"MT5 history validation failed for {source}: {validation}")
    timestamps = [row["timestamp"] for row in rows]
    numeric_timestamps = [value for value in timestamps if isinstance(value, int)]
    if len(numeric_timestamps) != len(timestamps) or any(
        left >= right for left, right in itertools.pairwise(numeric_timestamps)
    ):
        raise ValueError(f"MT5 timestamps must increase in {source}")
    frame = pd.DataFrame(rows)
    atr_values = atr(frame, 14).fillna((frame["high"] - frame["low"]).clip(lower=1e-12))
    candles = tuple(
        dict(row, atr14=float(value)) for row, value in zip(rows, atr_values)
    )
    if any(
        not isinstance(item.get("atr14"), (int, float))
        or not isfinite(cast(float, item["atr14"]))
        or cast(float, item["atr14"]) <= 0
        for item in candles
    ):
        raise ValueError(f"MT5 ATR enrichment failed for {source}")
    _ = requested_symbol
    return Dataset(
        resolved_symbol,
        timeframe,
        candles,
        validation.gaps,
        validation.duplicates,
        validation.invalid_rows,
    )


def load_mt5_datasets(data_dir: str | Path, coverage: Sequence[MT5Coverage]) -> tuple[Dataset, ...]:
    """Load exactly eight datasets named by coverage metadata."""
    if len(coverage) != len(MT5_SYMBOLS) * len(MT5_TIMEFRAMES):
        raise ValueError("MT5 research requires exactly eight coverage rows")
    expected_symbols = set(MT5_SYMBOLS)
    if {item.requested_symbol for item in coverage} != expected_symbols:
        raise ValueError("MT5 coverage must contain all requested symbols")
    if {item.timeframe for item in coverage} != set(MT5_TIMEFRAMES):
        raise ValueError("MT5 coverage must contain M15 and H1")
    expected_pairs = {(symbol, timeframe) for symbol in MT5_SYMBOLS for timeframe in MT5_TIMEFRAMES}
    if {(item.requested_symbol, item.timeframe) for item in coverage} != expected_pairs:
        raise ValueError("MT5 coverage must contain each requested symbol/timeframe pair")
    identities = {(item.resolved_symbol, item.timeframe) for item in coverage}
    if len(identities) != 8:
        raise ValueError("MT5 coverage contains duplicate dataset identities")
    root = Path(data_dir).resolve()
    datasets = tuple(
        _load_manifest_dataset(root, item)
        for item in coverage
    )
    if len({dataset.name for dataset in datasets}) != 8:
        raise ValueError("MT5 datasets contain duplicate identities")
    return datasets


def _load_manifest_dataset(root: Path, item: MT5Coverage) -> Dataset:
    source = Path(item.path) if Path(item.path).is_absolute() else root / Path(item.path).name
    dataset = load_mt5_dataset(source, item.requested_symbol, item.resolved_symbol, item.timeframe)
    validation = validate_history(dataset.candles, MT5_TIMEFRAMES[item.timeframe])
    actual = (len(dataset.candles), validation.start, validation.end, validation.gaps, validation.duplicates, validation.invalid_rows)
    expected = (item.rows, item.start, item.end, item.gaps, item.duplicates, item.invalid_rows)
    if actual != expected:
        raise ValueError(f"MT5 coverage metadata mismatch for {item.requested_symbol}_{item.timeframe}")
    return dataset


def load_coverage(path: str | Path) -> tuple[MT5Coverage, ...]:
    """Read fetch manifest and require point metadata."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("MT5 coverage must be a list")
    if len(raw) != len(MT5_SYMBOLS) * len(MT5_TIMEFRAMES):
        raise ValueError("MT5 coverage requires exactly eight rows")
    result: list[MT5Coverage] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("MT5 coverage rows must be objects")
        point = item.get("point")
        if (
            not isinstance(point, (int, float))
            or isinstance(point, bool)
            or not isfinite(float(point))
            or float(point) <= 0
        ):
            raise TypeError("MT5 coverage requires positive finite point metadata")
        result.append(
            MT5Coverage(
                str(item["requested_symbol"]),
                str(item["resolved_symbol"]),
                str(item["timeframe"]),
                str(item["path"]),
                float(point),
                _required_nonnegative_int(item.get("rows"), "rows"),
                _optional_string(item.get("start")),
                _optional_string(item.get("end")),
                _required_nonnegative_int(item.get("gaps"), "gaps"),
                _required_nonnegative_int(item.get("duplicates"), "duplicates"),
                _required_nonnegative_int(item.get("invalid_rows"), "invalid_rows"),
            )
        )
    if {item.requested_symbol for item in result} != set(MT5_SYMBOLS):
        raise ValueError("MT5 coverage must contain all requested symbols")
    if {item.timeframe for item in result} != set(MT5_TIMEFRAMES):
        raise ValueError("MT5 coverage must contain M15 and H1")
    return tuple(result)


def _required_nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError(f"MT5 coverage {field} must be a non-negative integer")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def run_mt5_research(
    datasets: Sequence[Dataset],
    points: Mapping[str, float],
    *,
    config: Config | None = None,
    coverage: Sequence[MT5Coverage] | None = None,
    commission_per_lot: float | None = None,
    random_runs: int = 200,
    random_seed: int = 510,
) -> MT5ResearchReport:
    """Run WX and YZ research over eight MT5 sets without execution APIs."""
    if len(datasets) != 8 or len({dataset.name for dataset in datasets}) != 8:
        raise ValueError("MT5 research requires eight unique datasets")
    loaded_config = config if config is not None else Config.load_from_env()
    if loaded_config.mt5_execution_enabled:
        raise ValueError("MT5 research requires execution disabled")
    configured_commission = (
        loaded_config.commission_per_lot if commission_per_lot is None else commission_per_lot
    )
    if not isfinite(configured_commission) or configured_commission < 0:
        raise ValueError("commission_per_lot must be non-negative and finite")

    def factory(dataset: Dataset) -> BacktestEngine:
        try:
            point = float(points[dataset.symbol])
        except KeyError as exc:
            raise ValueError(f"missing MT5 point for {dataset.symbol}") from exc
        return BacktestEngine(
            fee_rate=0.0,
            slippage_pct=0.0,
            cost_model=MT5CostModel(point, configured_commission, 1.0),
        )

    entry = run_research(
        datasets,
        engine_factory=factory,
        windows=5,
        random_runs=random_runs,
        random_seed=random_seed,
    )
    hypothesis = run_hypothesis_research(
        datasets,
        engine_factory=factory,
        random_runs=random_runs,
        random_seed=random_seed,
    )
    if coverage is None:
        coverage = tuple(
            MT5Coverage(
                dataset.symbol,
                dataset.symbol,
                dataset.interval,
                "",
                float(points[dataset.symbol]),
                len(dataset.candles),
                None,
                None,
                dataset.gaps,
                dataset.duplicates,
                dataset.invalid_rows,
            )
            for dataset in datasets
        )
    else:
        coverage = tuple(coverage)
        if len(coverage) != 8:
            raise ValueError("MT5 research requires exactly eight coverage rows")
    entry_decision = decide_mt5_entry(entry.reports)
    hypothesis_decision = decide_mt5_hypothesis(hypothesis.results)
    return MT5ResearchReport(
        entry,
        hypothesis,
        tuple(datasets),
        coverage,
        points,
        entry_decision,
        hypothesis_decision,
    )


def _coverage_for(coverage: Sequence[MT5Coverage], datasets: Sequence[Dataset], dataset_name: str) -> MT5Coverage:
    dataset = next(item for item in datasets if item.name == dataset_name)
    matches = [item for item in coverage if item.resolved_symbol == dataset.symbol and item.timeframe == dataset.interval]
    if len(matches) != 1:
        raise ValueError(f"coverage missing for {dataset_name}")
    return matches[0]


def _entry_rows(
    report: ResearchReport,
    metadata: Mapping[str, Dataset],
    points: Mapping[str, float],
    random_runs: int,
    coverage: Sequence[MT5Coverage],
    datasets: Sequence[Dataset],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in report.reports:
        dataset = metadata[item.dataset]
        rows.append({
            "dataset": item.dataset, "family": "WX", "variant": item.variant, "exit_model": "fixed_3r",
            "requested_symbol": _coverage_for(coverage, datasets, item.dataset).requested_symbol,
            "resolved_symbol": _coverage_for(coverage, datasets, item.dataset).resolved_symbol,
            "source_path": _coverage_for(coverage, datasets, item.dataset).path,
            "symbol": dataset.symbol, "timeframe": dataset.interval, "point": points[dataset.symbol],
            "rows": len(dataset.candles), "start": dataset.candles[0].get("timestamp"), "end": dataset.candles[-1].get("timestamp"),
            "gaps": dataset.gaps, "duplicates": dataset.duplicates, "invalid_rows": dataset.invalid_rows,
            "total_trades": item.total_trades, "mean_net_return_pct": item.mean_net_return_pct, "expectancy_r": item.mean_expectancy_r,
            "ci_low": item.expectancy_ci_low, "ci_high": item.expectancy_ci_high, "mean_sharpe": item.mean_sharpe,
            "max_drawdown_pct": item.max_drawdown_pct, "win_rate": item.win_rate, "profit_factor": item.profit_factor,
            "total_fees": item.total_fees, "total_slippage": item.total_slippage, "spread_cost_paid": item.total_spread_cost, "commission_paid": item.total_commission,
            "limit_fill_rate": item.limit_fill_rate, "random_mean_return_pct": item.random_mean_return_pct,
            "random_p90_return_pct": item.random_p90_return_pct, "random_runs": random_runs, "random_trade_count": item.random_trade_count,
            "insufficient": item.insufficient, "rank": item.variant,
        })
    return rows


def _hypothesis_rows(
    report: HypothesisResearchReport,
    metadata: Mapping[str, Dataset],
    points: Mapping[str, float],
    random_runs: int,
    coverage: Sequence[MT5Coverage],
    datasets: Sequence[Dataset],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in report.results:
        dataset = metadata[item.dataset]
        rows.append({
            "dataset": item.dataset, "family": "YZ", "variant": item.hypothesis, "exit_model": item.exit_model,
            "requested_symbol": _coverage_for(coverage, datasets, item.dataset).requested_symbol,
            "resolved_symbol": _coverage_for(coverage, datasets, item.dataset).resolved_symbol,
            "source_path": _coverage_for(coverage, datasets, item.dataset).path,
            "symbol": dataset.symbol, "timeframe": dataset.interval, "point": points[dataset.symbol],
            "rows": len(dataset.candles), "start": dataset.candles[0].get("timestamp"), "end": dataset.candles[-1].get("timestamp"),
            "gaps": dataset.gaps, "duplicates": dataset.duplicates, "invalid_rows": dataset.invalid_rows,
            "total_trades": item.total_trades, "mean_net_return_pct": item.mean_net_return_pct, "expectancy_r": item.expectancy_r,
            "ci_low": item.ci_low, "ci_high": item.ci_high, "mean_sharpe": item.sharpe, "max_drawdown_pct": item.max_drawdown_pct,
            "win_rate": item.win_rate, "profit_factor": item.profit_factor, "total_fees": item.total_fees, "total_slippage": item.total_slippage,
            "spread_cost_paid": sum(window.test_spread_cost for window in item.windows), "commission_paid": sum(window.test_commission for window in item.windows), "limit_fill_rate": item.limit_fill_rate,
            "random_mean_return_pct": item.random_mean_return_pct, "random_p90_return_pct": item.random_p90_return_pct,
            "random_runs": random_runs, "random_trade_count": item.random_trade_count, "insufficient": item.insufficient, "rank": item.rank,
        })
    return rows


REPORT_FIELDS = ("dataset", "family", "variant", "exit_model", "requested_symbol", "resolved_symbol", "source_path", "symbol", "timeframe", "point", "rows", "start", "end", "gaps", "duplicates", "invalid_rows", "total_trades", "mean_net_return_pct", "expectancy_r", "ci_low", "ci_high", "mean_sharpe", "max_drawdown_pct", "win_rate", "profit_factor", "total_fees", "total_slippage", "spread_cost_paid", "commission_paid", "limit_fill_rate", "random_mean_return_pct", "random_p90_return_pct", "random_runs", "random_trade_count", "insufficient", "rank")


def write_mt5_reports(
    report: MT5ResearchReport,
    markdown_path: str | Path,
    csv_path: str | Path,
    commission_per_lot: float = 0.0,
) -> None:
    """Write combined 152-row audit CSV and Markdown report."""
    metadata = {dataset.name: dataset for dataset in report.datasets}
    rows = _entry_rows(
        report.entry, metadata, report.points, report.entry.random_runs, report.coverage, report.datasets
    ) + _hypothesis_rows(
        report.hypothesis, metadata, report.points, report.hypothesis.random_runs, report.coverage, report.datasets
    )
    if len(rows) != 152:
        raise ValueError(f"expected 152 MT5 combinations, got {len(rows)}")
    target_csv = Path(csv_path)
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    with target_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    ranked = sorted(
        rows,
        key=lambda row: (
            -float(cast(float, row["ci_low"])),
            -float(cast(float, row["expectancy_r"])),
        ),
    )
    lines = [
        "# MT5 Research",
        "",
        "Research only; execution_enabled=false.",
        (
            f"Combinations tried: {len(rows)}; windows: 5; random runs: "
            f"{report.entry.random_runs}; bootstrap runs: {BOOTSTRAP_RUNS}."
        ),
        (
            f"Cost model: per-bar spread points × symbol point; 1-point market slippage; "
            f"commission_per_lot={commission_per_lot}; quantity_unit=research_lots."
        ),
        "",
        "## Coverage",
        "",
        "| Dataset | Rows | Start | End | Gaps | Duplicates | Invalid | Point |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for dataset in report.datasets:
        lines.append(
            f"| {dataset.name} | {len(dataset.candles)} | "
            f"{dataset.candles[0].get('timestamp')} | "
            f"{dataset.candles[-1].get('timestamp')} | {dataset.gaps} | "
            f"{dataset.duplicates} | {dataset.invalid_rows} | "
            f"{report.points[dataset.symbol]} |"
        )
    lines.extend(
        [
            "",
            "## Top 10",
            "",
            "| Family | Dataset | Variant | Exit | Trades | CI low | CI high | Expectancy R | Random P90 | Flag |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in ranked[:10]:
        lines.append(
            f"| {row['family']} | {row['dataset']} | {row['variant']} | {row['exit_model']} | "
            f"{row['total_trades']} | {float(cast(float, row['ci_low'])):.6f} | "
            f"{float(cast(float, row['ci_high'])):.6f} | "
            f"{float(cast(float, row['expectancy_r'])):.6f} | "
            f"{float(cast(float, row['random_p90_return_pct'])):.6f} | "
            f"{'INSUFFICIENT' if row['insufficient'] else 'OK'} |"
        )
    mx_entry = report.entry_decision or decide_mt5_entry(report.entry.reports)
    mx_hypothesis = report.hypothesis_decision or decide_mt5_hypothesis(report.hypothesis.results)
    lines.extend(
        [
            "",
            f"WX decision: {mx_entry.status} — {mx_entry.reason}",
            f"YZ decision: {mx_hypothesis.status} — {mx_hypothesis.reason}",
            "",
            "## Full combinations",
            "",
        ]
    )
    lines.extend(
        f"- {row['family']} {row['dataset']} {row['variant']}/{row['exit_model']}: "
        f"CI [{float(cast(float, row['ci_low'])):.6f}, "
        f"{float(cast(float, row['ci_high'])):.6f}], "
        f"expectancy R {float(cast(float, row['expectancy_r'])):.6f}, "
        f"trades {row['total_trades']}, "
        f"{'INSUFFICIENT' if row['insufficient'] else 'OK'}"
        for row in rows
    )
    target_md = Path(markdown_path)
    target_md.parent.mkdir(parents=True, exist_ok=True)
    target_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
