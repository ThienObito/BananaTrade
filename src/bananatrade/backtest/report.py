"""Backtest performance reports and CSV export."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, cast

from .engine import BacktestResult

REPORT_METRICS = (
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "win_rate",
    "total_trades",
)


def generate_report(result: BacktestResult) -> dict[str, Any]:
    """Return JSON-ready performance metrics and a human-readable summary."""
    return {
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "summary": (
            f"{result.total_trades} trades; return {result.total_return_pct:.2f}%; "
            f"max drawdown {result.max_drawdown_pct:.2f}%; Sharpe {result.sharpe_ratio:.2f}; "
            f"win rate {result.win_rate:.2f}%"
        ),
    }


def save_csv(result: BacktestResult, path: str | Path) -> tuple[Path, Path]:
    """Save equity curve and trade records beneath ``path``."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    equity_path = directory / "equity_curve.csv"
    trades_path = directory / "trades.csv"
    with equity_path.open("w", newline="", encoding="utf-8") as equity_handle:
        equity_writer = csv.writer(equity_handle)
        equity_writer.writerow(("index", "equity"))
        equity_writer.writerows((index, equity) for index, equity in enumerate(result.equity_curve))
    trade_fields = _trade_fields(result)
    with trades_path.open("w", newline="", encoding="utf-8") as trade_handle:
        writer = cast(csv.DictWriter[str], csv.DictWriter(trade_handle, fieldnames=trade_fields, extrasaction="ignore"))
        writer.writeheader()
        writer.writerows(result.trades)
    return equity_path, trades_path


def _trade_fields(result: BacktestResult) -> list[str]:
    fields = ["symbol", "side", "entry", "exit", "sl", "tp", "qty", "pnl", "reason"]
    for trade in result.trades:
        for key in trade:
            if key not in fields:
                fields.append(key)
    return fields
