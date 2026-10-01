from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from bananatrade.backtest.engine import BacktestEngine
from bananatrade.config import Config
from bananatrade.research.entry_ablation import Dataset
from bananatrade.research.mt5_decision import decide_mt5_entry
from bananatrade.research.mt5_research import (
    MT5Coverage,
    load_coverage,
    load_mt5_dataset,
    load_mt5_datasets,
    run_mt5_research,
)


def rows(count: int = 60) -> list[dict[str, object]]:
    return [
        {
            "timestamp": index * 900,
            "open": 100.0 + index * 0.01,
            "high": 101.0 + index * 0.01,
            "low": 99.0 + index * 0.01,
            "close": 100.0 + index * 0.01,
            "spread": 2.0,
            "tick_volume": 10.0,
            "real_volume": 10.0,
        }
        for index in range(count)
    ]


def write_csv(path: Path, values: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=values[0])
        writer.writeheader()
        writer.writerows(values)


def coverage_for(
    path: str,
    symbol: str = "XAUUSDm",
    timeframe: str = "M15",
    requested: str = "XAUUSD",
) -> MT5Coverage:
    return MT5Coverage(requested, symbol, timeframe, path, 0.01, 60, None, None, 0, 0, 0)


def test_loader_preserves_spread_and_adds_atr(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    write_csv(path, rows())
    dataset = load_mt5_dataset(path, "XAUUSD", "XAUUSDm", "M15")
    assert dataset.candles[0]["spread"] == 2.0
    assert all("atr14" in candle for candle in dataset.candles)


def test_loader_accepts_millisecond_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    values = rows()
    base = 1_700_000_000
    for value in values:
        value["timestamp"] = (base + int(value["timestamp"])) * 1000
    write_csv(path, values)
    dataset = load_mt5_dataset(path, "XAUUSD", "XAUUSDm", "M15")
    assert dataset.candles[1]["timestamp"] == 1_700_000_900


def test_loader_rejects_invalid_spread(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    values = rows()
    values[4]["spread"] = -1.0
    write_csv(path, values)
    with pytest.raises(ValueError, match="validation"):
        load_mt5_dataset(path, "XAUUSD", "XAUUSDm", "M15")


def test_coverage_loader_reads_point(tmp_path: Path) -> None:
    path = tmp_path / "coverage.json"
    values = []
    for symbol in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
        for timeframe in ("M15", "H1"):
            values.append(
                coverage_for(
                    f"mt5_{symbol}m_{timeframe}.csv",
                    f"{symbol}m",
                    timeframe,
                    symbol,
                ).__dict__
            )
    path.write_text(json.dumps(values), encoding="utf-8")
    loaded = load_coverage(path)
    assert len(loaded) == 8
    assert loaded[0].point == 0.01


def test_coverage_loader_requires_point(tmp_path: Path) -> None:
    path = tmp_path / "coverage.json"
    values = []
    for symbol in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
        for timeframe in ("M15", "H1"):
            values.append(
                coverage_for(
                    f"mt5_{symbol}m_{timeframe}.csv",
                    f"{symbol}m",
                    timeframe,
                    symbol,
                ).__dict__
            )
    del values[0]["point"]
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises((TypeError, ValueError), match="point"):
        load_coverage(path)


def test_dataset_loader_resolves_manifest_paths(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    path = history / "mt5_XAUUSDm_M15.csv"
    write_csv(path, rows())
    coverage = tuple(
        coverage_for("mt5_XAUUSDm_M15.csv") for _ in range(8)
    )
    with pytest.raises(ValueError, match="requested symbols"):
        load_mt5_datasets(history, coverage)


def test_mt5_decision_requires_eight_names() -> None:
    with pytest.raises(ValueError, match="dataset identities"):
        decide_mt5_entry((), dataset_count=8)


def test_research_requires_exactly_eight_datasets() -> None:
    dataset = Dataset("XAUUSDm", "M15", tuple(rows()))
    with pytest.raises(ValueError, match="eight"):
        run_mt5_research((dataset,), {"XAUUSDm": 0.01})


def test_research_rejects_enabled_config() -> None:
    datasets = tuple(
        Dataset(f"S{index}", "M15", tuple(rows())) for index in range(8)
    )
    points = {dataset.symbol: 0.01 for dataset in datasets}
    with pytest.raises(ValueError, match="execution disabled"):
        run_mt5_research(datasets, points, config=Config(mt5_execution_enabled=True))


def test_research_uses_loaded_commission() -> None:
    datasets = tuple(
        Dataset(f"S{index}", "M15", tuple(rows())) for index in range(8)
    )
    points = {dataset.symbol: 0.01 for dataset in datasets}
    report = run_mt5_research(
        datasets,
        points,
        config=Config(commission_per_lot=3.5),
        random_runs=1,
    )
    assert report.points == points


def test_engine_factory_selects_symbol_cost_model() -> None:
    seen: list[float] = []

    def factory(dataset: Dataset) -> BacktestEngine:
        seen.append(0.01 if dataset.symbol == "XAUUSDm" else 0.00001)
        return BacktestEngine(fee_rate=0.0, slippage_pct=0.0)

    dataset = Dataset("XAUUSDm", "M15", tuple(rows(60)))
    from bananatrade.research.entry_ablation import run_research

    run_research((dataset,), engine_factory=factory, random_runs=1)
    assert seen == [0.01]


def test_report_writer_rejects_non_152_rows(tmp_path: Path) -> None:
    dataset = Dataset("XAUUSDm", "M15", tuple(rows(60)))
    with pytest.raises(ValueError, match="eight"):
        run_mt5_research((dataset,), {"XAUUSDm": 0.01})
    _ = BacktestEngine
