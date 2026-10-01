"""Walk-forward research across entry hypotheses and exit models."""

from __future__ import annotations

import csv
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean
from typing import TYPE_CHECKING

from ..backtest.engine import BacktestEngine, BacktestResult
from ..engine.strategy import SignalResult
from .entry_ablation import (
    Dataset,
    WindowMetrics,
    _bootstrap_ci,
    _buy_hold_return_from_candles,
    _number,
    _split_windows,
)
from .hypotheses import EXIT_MODELS, HYPOTHESES, HypothesisStrategy, top_volume_hours

if TYPE_CHECKING:
    from .hypothesis_decision import HypothesisDecision


@dataclass(frozen=True)
class HypothesisResult:
    dataset: str
    hypothesis: str
    exit_model: str
    windows: tuple[WindowMetrics, ...]
    total_trades: int
    mean_net_return_pct: float
    expectancy_r: float
    ci_low: float
    ci_high: float
    max_drawdown_pct: float
    sharpe: float
    win_rate: float
    profit_factor: float
    total_fees: float
    total_slippage: float
    limit_fill_rate: float
    random_mean_return_pct: float
    random_p90_return_pct: float
    random_trade_count: int
    insufficient: bool
    total_spread_cost: float = 0.0
    total_commission: float = 0.0
    rank: int = 0

    @property
    def key(self) -> str:
        return f"{self.hypothesis}/{self.exit_model}"


@dataclass(frozen=True)
class HypothesisResearchReport:
    results: tuple[HypothesisResult, ...]
    combinations_tried: int
    random_runs: int
    random_seed: int
    decision: HypothesisDecision

    @property
    def ranking(self) -> tuple[HypothesisResult, ...]:
        return tuple(sorted(self.results, key=lambda item: (-item.ci_low, -item.expectancy_r)))


def run_hypothesis_research(
    datasets: Sequence[Dataset],
    *,
    engine: BacktestEngine | None = None,
    engine_factory: Callable[[Dataset], BacktestEngine] | None = None,
    random_runs: int = 200,
    random_seed: int = 510,
) -> HypothesisResearchReport:
    if not datasets:
        raise ValueError("datasets must not be empty")
    if random_runs <= 0:
        raise ValueError("random_runs must be positive")
    if engine is not None and engine_factory is not None:
        raise ValueError("engine and engine_factory are mutually exclusive")
    results: list[HypothesisResult] = []
    for dataset_index, dataset in enumerate(datasets):
        backtester = engine_factory(dataset) if engine_factory is not None else engine or BacktestEngine()
        windows = _split_windows(dataset.candles, 5)
        for combination_index, hypothesis in enumerate(HYPOTHESES):
            for exit_index, exit_model in enumerate(EXIT_MODELS):
                metrics: list[WindowMetrics] = []
                opportunities: list[tuple[list[dict[str, object]], tuple[int, ...]]] = []
                for window_index, (train, test, train_start, train_end, test_start, test_end) in enumerate(windows, 1):
                    allowed = top_volume_hours(train) if hypothesis == "H4" else None
                    strategy = HypothesisStrategy(hypothesis, allowed_hours=allowed)
                    prefix_len = min(strategy.lookback, len(train))
                    context = list(train[-prefix_len:]) + list(test)
                    result = backtester.run(context, strategy, exit_model=exit_model, stop_atr_multiplier=1.5, partial_take_profit=False)
                    result.trades[:] = [
                        trade for trade in result.trades if _trade_index(trade) >= prefix_len
                    ]
                    result.trades[:] = [
                        dict(trade, entry_index=_trade_index(trade) - prefix_len + test_start, signal_index=_signal_index(trade) - prefix_len + test_start)
                        for trade in result.trades
                    ]
                    metrics.append(
                        _metrics(
                            window_index,
                            train_start,
                            train_end,
                            test_start,
                            test_end,
                            result,
                            test,
                        )
                    )
                    indices = tuple(_signal_index(trade) - test_start for trade in result.trades)
                    opportunities.append((test, indices))

                random_returns: list[float] = []
                random_trade_count = 0
                seed_base = random_seed + dataset_index * 10_000 + combination_index * 100 + exit_index
                for trial in range(random_runs):
                    trial_returns: list[float] = []
                    for window_index, (test, indices) in enumerate(opportunities):
                        rng = random.Random(seed_base + trial * 10 + window_index)
                        random_result = backtester.run(
                            test,
                            _RandomAtIndices(rng, indices),
                            exit_model=exit_model,
                            stop_atr_multiplier=1.5,
                            partial_take_profit=False,
                            partial_take_profit_r=1.0,
                            trailing_r=1.0,
                        )
                        trial_returns.append(random_result.net_total_return_pct)
                        random_trade_count += random_result.total_trades
                    random_returns.append(mean(trial_returns) if trial_returns else 0.0)

                samples = tuple(value for item in metrics for value in item.test_r_samples)
                ci_low, ci_high = _bootstrap_ci(samples, seed_base)
                random_ordered = sorted(random_returns)
                p90_index = min(len(random_ordered) - 1, max(0, math.ceil(len(random_ordered) * 0.9) - 1))
                total_trades = sum(item.test_trades for item in metrics)
                losses = sum(item.test_net_losses for item in metrics)
                gains = sum(item.test_net_gains for item in metrics)
                results.append(
                    HypothesisResult(
                        dataset.name,
                        hypothesis,
                        exit_model,
                        tuple(metrics),
                        total_trades,
                        mean(item.test_net_return_pct for item in metrics),
                        mean(samples) if samples else 0.0,
                        ci_low,
                        ci_high,
                        max(item.test_max_drawdown_pct for item in metrics),
                        mean(item.test_sharpe for item in metrics),
                        sum(item.test_win_rate * item.test_trades for item in metrics) / total_trades
                        if total_trades
                        else 0.0,
                        gains / losses if losses else (float("inf") if gains else 0.0),
                        sum(item.test_fees for item in metrics),
                        sum(item.test_slippage for item in metrics),
                        sum(item.test_limit_fills for item in metrics)
                        / sum(item.test_limit_orders for item in metrics)
                        if sum(item.test_limit_orders for item in metrics)
                        else 0.0,
                        mean(random_returns),
                        random_ordered[p90_index],
                        random_trade_count,
                        any(item.test_insufficient for item in metrics),
                        sum(item.test_spread_cost for item in metrics),
                        sum(item.test_commission for item in metrics),
                    )
                )
    ranked = tuple(
        replace(result, rank=rank)
        for rank, result in enumerate(sorted(results, key=lambda item: (-item.ci_low, -item.expectancy_r)), 1)
    )
    from .hypothesis_decision import decide_hypothesis_default

    decision = decide_hypothesis_default(ranked, len(datasets))
    return HypothesisResearchReport(ranked, len(ranked), random_runs, random_seed, decision)


class _RandomAtIndices:
    lookback = 1

    def __init__(self, rng: random.Random, indices: Sequence[int]) -> None:
        self.rng = rng
        self.indices = frozenset(indices)
        self.index = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        current = self.index
        self.index += 1
        if current not in self.indices:
            return SignalResult("NEUTRAL", 0.0, "random null")
        return SignalResult("LONG" if self.rng.randrange(2) == 0 else "SHORT", 0.5, "random entry")


def _metrics(
    window: int,
    train_start: int,
    train_end: int,
    test_start: int,
    test_end: int,
    result: BacktestResult,
    candles: Sequence[dict[str, object]],
) -> WindowMetrics:
    primary_trades = _primary_trades(result.trades)
    samples = tuple(_number(trade.get("r_multiple")) for trade in primary_trades)
    net_values = tuple(_number(trade.get("net_pnl")) for trade in primary_trades)
    gains = sum(value for value in net_values if value > 0)
    losses = -sum(value for value in net_values if value < 0)
    return WindowMetrics(
        window,
        train_start,
        train_end,
        test_start,
        test_end,
        0.0,
        result.total_return_pct,
        result.net_total_return_pct,
        mean(samples) if samples else 0.0,
        result.net_sharpe_ratio,
        result.net_max_drawdown_pct,
        len(primary_trades),
        result.fees_paid,
        sum(value > 0 for value in net_values) / len(net_values) * 100 if net_values else 0.0,
        gains / losses if losses else (float("inf") if gains else 0.0),
        result.total_trades < 30,
        samples,
        gains,
        losses,
        result.limit_orders,
        result.limit_fills,
        result.slippage_paid,
        _buy_hold_return_from_candles(candles),
        result.spread_cost_paid,
        result.commission_paid,
    )


def _primary_trades(trades: Sequence[dict[str, object]]) -> tuple[dict[str, object], ...]:
    grouped: dict[object, dict[str, object]] = {}
    for trade in trades:
        key = trade.get("position_id", id(trade))
        current = grouped.get(key)
        if current is None:
            grouped[key] = dict(trade)
            continue
        for field in ("net_pnl", "gross_pnl", "pnl", "fees", "spread_cost", "commission_cost", "slippage_cost"):
            current[field] = _number(current.get(field, 0.0)) + _number(trade.get(field, 0.0))
        current["qty"] = _number(current.get("qty", 0.0)) + _number(trade.get("qty", 0.0))
    return tuple(grouped.values())


def _signal_index(trade: dict[str, object]) -> int:
    value = trade.get("signal_index")
    return value if isinstance(value, int) else -1


def _trade_index(trade: dict[str, object]) -> int:
    value = trade.get("entry_index")
    return value if isinstance(value, int) else -1


def write_hypothesis_reports(report: HypothesisResearchReport, markdown_path: str, csv_path: str) -> None:
    fields = [
        "rank", "dataset", "hypothesis", "exit_model", "total_trades", "mean_net_return_pct",
        "expectancy_r", "ci_low", "ci_high", "max_drawdown_pct", "sharpe", "win_rate",
        "profit_factor", "total_fees", "total_slippage", "total_spread_cost", "total_commission",
        "limit_fill_rate", "random_mean_return_pct", "random_p90_return_pct", "random_trade_count",
        "insufficient",
    ]
    csv_file = Path(csv_path)
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in report.ranking:
            writer.writerow({field: getattr(result, field) for field in fields})
    lines = [
        "# Entry Hypothesis Research",
        "",
        f"Combinations tried: {report.combinations_tried}; random runs: {report.random_runs}; seed: {report.random_seed}",
        "",
    ]
    for result in report.ranking:
        lines.append(
            f"- {result.rank} {result.dataset} {result.hypothesis}/{result.exit_model}: "
            f"CI [{result.ci_low:.4f}, {result.ci_high:.4f}], "
            f"expectancy {result.expectancy_r:.4f}, "
            f"{'INSUFFICIENT' if result.insufficient else 'OK'}"
        )
    lines.extend(["", f"Decision: {report.decision.status}", f"Reason: {report.decision.reason}"])
    markdown_file = Path(markdown_path)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
