"""Fixed-rule out-of-sample entry ablation and reproducible benchmarks."""

from __future__ import annotations

import csv
import itertools
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean
from typing import TYPE_CHECKING, Literal

from ..backtest.engine import BacktestEngine, BacktestResult
from ..engine.strategy import SignalResult
from .hypotheses import _higher_timeframe_closes

if TYPE_CHECKING:
    from .decision import Decision

VariantName = Literal["V0", "V1", "V2", "V3", "V4", "V5", "V6"]
VARIANTS: tuple[VariantName, ...] = ("V0", "V1", "V2", "V3", "V4", "V5", "V6")
WINDOW_COUNT = 5
MIN_TRADES_PER_WINDOW = 30
BOOTSTRAP_RUNS = 2_000
VARIANT_DEFINITIONS: dict[str, str] = {
    "V0": "MA-cross signal with market entry",
    "V1": "V0 plus directional regime filter",
    "V2": "V1 plus confidence gate >= 0.65",
    "V3": "V2 plus 0.30 ATR limit entry",
    "V4": "V3 plus 50% TP1 and 1R trailing remainder",
    "V5": "V0 plus higher-timeframe confirmation",
    "V6": "V0 plus regime, confidence, 0.30 ATR limit, partial TP, and MTF confirmation",
}


@dataclass(frozen=True)
class Dataset:
    """One downloaded symbol/interval dataset."""

    symbol: str
    interval: str
    candles: tuple[dict[str, object], ...]
    gaps: int = 0
    duplicates: int = 0
    invalid_rows: int = 0

    @property
    def name(self) -> str:
        return f"{self.symbol}_{self.interval}"


@dataclass(frozen=True)
class WindowMetrics:
    """One chronological train/test result."""

    window: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_return_pct: float
    test_return_pct: float
    test_net_return_pct: float
    test_expectancy_r: float
    test_sharpe: float
    test_max_drawdown_pct: float
    test_trades: int
    test_fees: float
    test_win_rate: float
    test_profit_factor: float
    test_insufficient: bool
    test_r_samples: tuple[float, ...] = ()
    test_net_gains: float = 0.0
    test_net_losses: float = 0.0
    test_limit_orders: int = 0
    test_limit_fills: int = 0
    test_slippage: float = 0.0
    buy_hold_return_pct: float = 0.0
    test_spread_cost: float = 0.0
    test_commission: float = 0.0
    test_equity_curve: tuple[float, ...] = ()

    @property
    def test_limit_fill_rate(self) -> float:
        """Return filled limit orders divided by submitted orders."""
        return self.test_limit_fills / self.test_limit_orders if self.test_limit_orders else 0.0


@dataclass(frozen=True)
class VariantReport:
    """Aggregate out-of-sample metrics for one variant and dataset."""

    dataset: str
    variant: str
    windows: tuple[WindowMetrics, ...]
    total_trades: int
    mean_return_pct: float
    mean_net_return_pct: float
    mean_expectancy_r: float
    expectancy_ci_low: float
    mean_sharpe: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    insufficient: bool
    buy_hold_return_pct: float
    random_p90_return_pct: float
    random_mean_return_pct: float
    random_seed: int
    expectancy_ci_high: float = 0.0
    expectancy_sample_count: int = 0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    limit_fill_rate: float = 0.0
    random_trade_count: int = 0
    total_spread_cost: float = 0.0
    total_commission: float = 0.0


@dataclass(frozen=True)
class ResearchReport:
    """All datasets, variants, benchmarks, and decision evidence."""

    reports: tuple[VariantReport, ...]
    random_runs: int
    random_seed: int
    window_count: int
    decision: Decision

    def by_dataset(self, dataset: str) -> tuple[VariantReport, ...]:
        return tuple(report for report in self.reports if report.dataset == dataset)

    def proven_variants(self) -> tuple[str, ...]:
        """Return variants passing centralized evidence gates."""
        return tuple(item.variant for item in self.decision.gate_evidence if item.passed)


class AblationStrategy:
    """Causal signal generator implementing exact V0-V6 definitions."""

    lookback = 80
    fast_period = 20
    slow_period = 50

    def __init__(self, variant: VariantName, warmup_bars: int = 0) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"unsupported variant: {variant}")
        self.variant = variant
        self.warmup_bars = warmup_bars
        self._calls = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        self._calls += 1
        closes = [_number(candle.get("close")) for candle in candles]
        required = max(self.slow_period + 1, self.warmup_bars)
        if len(closes) < required or (self.variant in {"V3", "V4", "V6"} and len(closes) < 4):
            return SignalResult("NEUTRAL", 0.0, f"{self.variant}: warmup")
        direction = self._direction(closes)
        if direction == 0:
            direction = 1 if closes[-1] > closes[-2] else -1 if closes[-1] < closes[-2] else 0
            if direction == 0:
                return SignalResult("NEUTRAL", 0.0, f"{self.variant}: no MA cross")
        bias: Literal["LONG", "SHORT"] = "LONG" if direction > 0 else "SHORT"
        atr14 = _atr(candles[-1], closes[-1])
        fast, slow = self._moving_averages(closes)
        confidence = min(1.0, 0.5 + abs(fast - slow) / max(atr14 * 2.0, 1e-12))
        regime_ok = self._regime_ok(closes, bias, atr14)
        uses_regime = self.variant in {"V1", "V2", "V3", "V4", "V6"}
        uses_confidence = self.variant in {"V2", "V3", "V4", "V6"}
        uses_mtf = self.variant in {"V5", "V6"}
        if uses_regime and not regime_ok:
            return SignalResult("NEUTRAL", confidence, f"{self.variant}: regime filter")
        if uses_confidence and confidence < 0.65 and len(closes) >= self.slow_period + 1:
            return SignalResult("NEUTRAL", confidence, f"{self.variant}: confidence below 0.65")
        if uses_mtf and len(closes) >= 10 and not self._mtf_confirmed(candles, bias):
            return SignalResult("NEUTRAL", confidence, f"{self.variant}: MTF filter")
        mode: Literal["market", "limit"] = "market"
        limit_price: float | None = None
        if self.variant in {"V3", "V4", "V6"}:
            mode = "limit"
            offset = 0.3 * atr14
            limit_price = closes[-1] - offset if bias == "LONG" else closes[-1] + offset
        return SignalResult(bias, confidence, f"{self.variant}: {mode}", mode, limit_price)

    def _direction(self, closes: list[float]) -> int:
        if len(closes) < self.slow_period + 1:
            return 1 if closes[-1] > closes[-2] else -1 if closes[-1] < closes[-2] else 0
        previous_fast = mean(closes[-self.fast_period - 1 : -1])
        previous_slow = mean(closes[-self.slow_period - 1 : -1])
        current_fast = mean(closes[-self.fast_period :])
        current_slow = mean(closes[-self.slow_period :])
        if previous_fast <= previous_slow and current_fast > current_slow:
            return 1
        if previous_fast >= previous_slow and current_fast < current_slow:
            return -1
        return 0

    def _moving_averages(self, closes: list[float]) -> tuple[float, float]:
        fast = mean(closes[-min(self.fast_period, len(closes)) :])
        slow = mean(closes[-min(self.slow_period, len(closes)) :])
        return fast, slow

    @staticmethod
    def _regime_ok(closes: list[float], bias: str, atr14: float) -> bool:
        if len(closes) < 5:
            return True
        slope = closes[-1] - closes[-5]
        threshold = max(atr14 * 0.05, 1e-12)
        return slope >= threshold if bias == "LONG" else slope <= -threshold

    @staticmethod
    def _mtf_confirmed(candles: list[dict[str, object]], bias: str) -> bool:
        higher = _higher_timeframe_closes(candles)
        if len(higher) < 2:
            return False
        previous = higher[-2]
        current = higher[-1]
        return current > previous if bias == "LONG" else current < previous


class RandomEntryStrategy:
    """Random direction at predetermined entry opportunities."""

    lookback = 1

    def __init__(self, rng: random.Random, entry_indices: Sequence[int] | None = None) -> None:
        self.rng = rng
        self.entry_indices = frozenset(entry_indices or ())
        self.all_entries = entry_indices is None
        self.index = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        current = self.index
        self.index += 1
        if not self.all_entries and current not in self.entry_indices:
            return SignalResult("NEUTRAL", 0.0, "random-entry null")
        bias: Literal["LONG", "SHORT"] = "LONG" if self.rng.randrange(2) == 0 else "SHORT"
        return SignalResult(bias, 0.5, "same-count fixed-seed random")


class RandomStrategy(RandomEntryStrategy):
    """Backward-compatible random strategy with one opportunity per bar."""

    def __init__(self, rng: random.Random) -> None:
        super().__init__(rng)


def run_research(
    datasets: Sequence[Dataset],
    *,
    engine: BacktestEngine | None = None,
    engine_factory: Callable[[Dataset], BacktestEngine] | None = None,
    windows: int = WINDOW_COUNT,
    random_runs: int = 200,
    random_seed: int = 510,
) -> ResearchReport:
    """Run five disjoint 70/30 fixed-rule chronological OOS tests."""
    if not datasets:
        raise ValueError("datasets must not be empty")
    if windows <= 0:
        raise ValueError("windows must be positive")
    if windows != WINDOW_COUNT:
        raise ValueError("windows must be five")
    if random_runs <= 0:
        raise ValueError("random_runs must be positive")
    if engine is not None and engine_factory is not None:
        raise ValueError("engine and engine_factory are mutually exclusive")
    _validate_dataset_identities(datasets)
    reports: list[VariantReport] = []
    for dataset in datasets:
        _validate_dataset(dataset)
        backtester = engine_factory(dataset) if engine_factory is not None else engine or BacktestEngine()
        windows_data = _split_windows(dataset.candles, windows)
        for variant_index, variant in enumerate(VARIANTS):
            metrics: list[WindowMetrics] = []
            test_results: list[BacktestResult] = []
            for index, (train, test, train_start, train_end, test_start, test_end) in enumerate(windows_data, 1):
                train_strategy = AblationStrategy(variant)
                train_context = list(train)
                train_result = backtester.run(train_context, train_strategy, partial_take_profit=_uses_partial(variant), partial_take_profit_r=1.0, trailing_r=1.0)
                test_strategy = AblationStrategy(variant)
                prefix = list(train[-test_strategy.lookback :])
                test_result = backtester.run(prefix + list(test), test_strategy, partial_take_profit=_uses_partial(variant), partial_take_profit_r=1.0, trailing_r=1.0)
                test_result = _oos_result(test_result, len(prefix), test)
                test_result.trades[:] = [
                    dict(
                        trade,
                        entry_index=_trade_index(trade) - len(prefix) + test_start,
                        signal_index=_signal_index(trade) - len(prefix) + test_start,
                    )
                    for trade in test_result.trades
                    if _trade_index(trade) >= len(prefix)
                ]
                metrics.append(_window_metrics(index, train_start, train_end, test_start, test_end, train_result, test_result, test))
                test_results.append(test_result)
            benchmark = _benchmarks_for_windows(
                backtester,
                windows_data,
                test_results,
                random_runs,
                random_seed + variant_index,
            )
            reports.append(_aggregate(dataset.name, variant, metrics, benchmark, random_seed + variant_index))
    from .decision import decide_default

    decision = decide_default(tuple(reports), len(datasets))
    return ResearchReport(tuple(reports), random_runs, random_seed, windows, decision)


def write_reports(report: ResearchReport, markdown_path: str | Path, csv_path: str | Path) -> None:
    """Write aggregate and per-window audit tables."""
    markdown = [
        "# Entry Research",
        "",
        f"Windows: {report.window_count}; random runs: {report.random_runs}; seed: {report.random_seed}",
        f"Minimum trades per OOS window: {MIN_TRADES_PER_WINDOW}; bootstrap runs: {BOOTSTRAP_RUNS}",
        "",
        "Variant definitions:",
    ]
    markdown.extend(f"- {variant}: {VARIANT_DEFINITIONS[variant]}" for variant in VARIANTS)
    markdown.extend([
        "",
        "| Dataset | Variant | Trades | Mean OOS net % | Expectancy R | CI low | CI high | Fees | Limit fill % | Random mean % | Random P90 % | Flag |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    fields = [
        "dataset", "variant", "total_trades", "mean_return_pct", "mean_net_return_pct", "mean_expectancy_r",
        "expectancy_ci_low", "expectancy_ci_high", "expectancy_sample_count", "mean_sharpe", "max_drawdown_pct",
        "win_rate", "profit_factor", "insufficient", "total_fees", "total_slippage", "total_spread_cost", "total_commission", "limit_fill_rate",
        "buy_hold_return_pct", "random_mean_return_pct", "random_p90_return_pct", "random_trade_count", "random_seed",
    ]
    path_csv = Path(csv_path)
    path_csv.parent.mkdir(parents=True, exist_ok=True)
    with path_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report.reports:
            writer.writerow({field: getattr(item, field) for field in fields})
            markdown.append(
                f"| {item.dataset} | {item.variant} | {item.total_trades} | {item.mean_net_return_pct:.4f} | "
                f"{item.mean_expectancy_r:.4f} | {item.expectancy_ci_low:.4f} | {item.expectancy_ci_high:.4f} | "
                f"{item.total_fees:.4f} | {item.limit_fill_rate:.4f} | {item.random_mean_return_pct:.4f} | "
                f"{item.random_p90_return_pct:.4f} | {'INSUFFICIENT' if item.insufficient else 'OK'} |"
            )
    markdown.extend([
        "",
        "## OOS windows",
        "",
        "| Dataset | Variant | Window | Train range | Test range | Trades | Net % | Expectancy R | CI flag | Fees | Limit fill % | Buy-hold % |",
        "|---|---|---:|---|---|---:|---:|---:|---|---:|---:|---:|",
    ])
    for item in report.reports:
        for window in item.windows:
            markdown.append(
                f"| {item.dataset} | {item.variant} | {window.window} | {window.train_start}:{window.train_end} | "
                f"{window.test_start}:{window.test_end} | {window.test_trades} | {window.test_net_return_pct:.4f} | "
                f"{window.test_expectancy_r:.4f} | {'INSUFFICIENT' if window.test_insufficient else 'OK'} | "
                f"{window.test_fees:.4f} | {window.test_limit_fill_rate:.4f} | {window.buy_hold_return_pct:.4f} |"
            )
    decision = report.decision
    markdown.extend([
        "",
        f"Decision evidence: {decision.status}",
        f"Decision: {decision.status}",
        f"Selected variant: {decision.selected_variant or 'none'}",
        f"Reason: {decision.reason}",
        f"Evidence datasets ({decision.dataset_count}): {', '.join(decision.dataset_names)}",
        "",
        "| Variant | Evidence complete | Positive CI datasets | Random-P90 datasets | Sufficient datasets | Passed | Rejection reasons |",
        "|---|---|---:|---:|---:|---|---|",
    ])
    for gate in decision.gate_evidence:
        markdown.append(
            f"| {gate.variant} | {gate.complete_dataset_evidence} | {gate.positive_expectancy_ci} | "
            f"{gate.beats_random_p90} | {gate.sufficient_trades} | {gate.passed} | "
            f"{', '.join(gate.rejection_reasons) or 'none'} |"
        )
    path_md = Path(markdown_path)
    path_md.parent.mkdir(parents=True, exist_ok=True)
    path_md.write_text("\n".join(markdown) + "\n", encoding="utf-8")


def _split_windows(candles: Sequence[dict[str, object]], count: int) -> list[tuple[list[dict[str, object]], list[dict[str, object]], int, int, int, int]]:
    if count != WINDOW_COUNT:
        raise ValueError("windows must be five")
    if len(candles) < count * 10:
        raise ValueError("dataset too short for five 70/30 windows")
    size = len(candles) // count
    result: list[tuple[list[dict[str, object]], list[dict[str, object]], int, int, int, int]] = []
    for index in range(count):
        start = index * size
        end = len(candles) if index == count - 1 else (index + 1) * size
        span = end - start
        train_length = max(1, min(span - 1, math.floor(span * 0.7)))
        train_end = start + train_length
        if train_end <= start or train_end >= end:
            raise ValueError("window must contain non-empty train and test data")
        result.append((list(candles[start:train_end]), list(candles[train_end:end]), start, train_end, train_end, end))
    return result


def _oos_result(result: BacktestResult, prefix: int, test: Sequence[dict[str, object]]) -> BacktestResult:
    """Remove warmup bars from trade and curve evidence."""
    trades = [trade for trade in result.trades if _trade_index(trade) >= prefix]
    trades = [dict(trade, entry_index=_trade_index(trade) - prefix, signal_index=_signal_index(trade) - prefix) for trade in trades]
    curve = result.equity_curve[prefix:] if len(result.equity_curve) > prefix else result.equity_curve
    net_curve = result.net_equity_curve[prefix:] if result.net_equity_curve and len(result.net_equity_curve) > prefix else result.net_equity_curve
    return replace(result, trades=trades, total_trades=len(trades), equity_curve=curve, net_equity_curve=net_curve)


def _window_metrics(
    index: int,
    train_start: int,
    train_end: int,
    test_start: int,
    test_end: int,
    train: BacktestResult,
    test: BacktestResult,
    test_candles: Sequence[dict[str, object]],
) -> WindowMetrics:
    primary_trades = _primary_trades(test.trades)
    samples = tuple(_number(trade.get("r_multiple")) for trade in primary_trades)
    net_values = tuple(_number(trade.get("net_pnl")) for trade in primary_trades)
    gains = sum(value for value in net_values if value > 0)
    losses = -sum(value for value in net_values if value < 0)
    net_wins = sum(1 for value in net_values if value > 0)
    return WindowMetrics(
        index,
        train_start,
        train_end,
        test_start,
        test_end,
        train.net_total_return_pct,
        test.total_return_pct,
        test.net_total_return_pct,
        mean(samples) if samples else 0.0,
        test.net_sharpe_ratio,
        test.net_max_drawdown_pct,
        len(primary_trades),
        test.fees_paid,
        net_wins / len(net_values) * 100 if net_values else 0.0,
        gains / losses if losses else (float("inf") if gains else 0.0),
        test.total_trades < MIN_TRADES_PER_WINDOW,
        samples,
        gains,
        losses,
        test.limit_orders,
        test.limit_fills,
        test.slippage_paid,
        _buy_hold_return_from_candles(test_candles),
        test.spread_cost_paid,
        test.commission_paid,
        tuple(test.net_equity_curve or test.equity_curve),
    )


def _aggregate(
    dataset: str,
    variant: str,
    windows: list[WindowMetrics],
    benchmark: tuple[float, float, int, float],
    seed: int,
) -> VariantReport:
    samples = tuple(value for item in windows for value in item.test_r_samples)
    ci_low, ci_high = _bootstrap_ci(samples, seed)
    curves: list[float] = [10_000.0]
    for item in windows:
        if item.test_equity_curve:
            start = item.test_equity_curve[0]
            scale = curves[-1] / start if start > 0 else 1.0
            curves.extend(value * scale for value in item.test_equity_curve[1:])
        else:
            curves.append(curves[-1] * (1.0 + item.test_net_return_pct / 100.0))
    peak = curves[0]
    drawdown = 0.0
    for value in curves:
        peak = max(peak, value)
        drawdown = max(drawdown, (peak - value) / peak * 100.0 if peak else 0.0)
    total_trades = sum(item.test_trades for item in windows)
    total_limit_orders = sum(item.test_limit_orders for item in windows)
    total_limit_fills = sum(item.test_limit_fills for item in windows)
    return VariantReport(
        dataset,
        variant,
        tuple(windows),
        total_trades,
        mean(item.test_return_pct for item in windows),
        mean(item.test_net_return_pct for item in windows),
        mean(samples) if samples else 0.0,
        ci_low,
        mean(item.test_sharpe for item in windows),
        drawdown,
        sum(item.test_win_rate * item.test_trades for item in windows) / total_trades if total_trades else 0.0,
        sum(item.test_net_gains for item in windows) / sum(item.test_net_losses for item in windows)
        if sum(item.test_net_losses for item in windows) > 0
        else (float("inf") if sum(item.test_net_gains for item in windows) > 0 else 0.0),
        any(item.test_insufficient for item in windows),
        mean(item.buy_hold_return_pct for item in windows),
        benchmark[1],
        benchmark[0],
        seed,
        ci_high,
        len(samples),
        sum(item.test_fees for item in windows),
        sum(item.test_slippage for item in windows),
        total_limit_fills / total_limit_orders if total_limit_orders else 0.0,
        benchmark[2],
        sum(item.test_spread_cost for item in windows),
        sum(item.test_commission for item in windows),
    )


def _benchmarks_for_windows(
    engine: BacktestEngine,
    windows: Sequence[tuple[list[dict[str, object]], list[dict[str, object]], int, int, int, int]],
    variant_results: Sequence[BacktestResult],
    runs: int,
    seed: int,
) -> tuple[float, float, int, float]:
    target_indices = [
        tuple(
            sorted(
                {
                    value - test_start
                    for trade in result.trades
                    if isinstance((value := trade.get("signal_index")), int)
                }
            )
        )
        for result, (_, _, _, _, test_start, _) in zip(variant_results, windows)
    ]
    target_count = sum(len(indices) for indices in target_indices)
    values: list[float] = []
    for run_index in range(runs):
        window_returns: list[float] = []
        for window_index, (_, test, _, _, _, _) in enumerate(windows):
            result = engine.run(
                test,
                RandomEntryStrategy(random.Random(seed + run_index * WINDOW_COUNT + window_index), target_indices[window_index]),
            )
            window_returns.append(result.net_total_return_pct)
        values.append(mean(window_returns) if window_returns else 0.0)
    ordered = sorted(values)
    percentile_index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.9) - 1))
    return mean(values), ordered[percentile_index], target_count, _bootstrap_ci(values, seed)[0]


def _benchmarks(engine: BacktestEngine, candles: Sequence[dict[str, object]], runs: int, seed: int) -> tuple[float, float, float, int]:
    """Backward-compatible full-series random benchmark without return clipping."""
    values = [engine.run(list(candles), RandomStrategy(random.Random(seed + index))).net_total_return_pct for index in range(runs)]
    ordered = sorted(values)
    percentile_index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.9) - 1))
    return mean(values), ordered[percentile_index], _buy_hold_return_from_candles(candles), seed


def _bootstrap_ci(values: Sequence[float], seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    means = [mean(rng.choice(values) for _ in values) for _ in range(BOOTSTRAP_RUNS)]
    ordered = sorted(means)
    low_index = math.floor(0.025 * (len(ordered) - 1))
    high_index = math.ceil(0.975 * (len(ordered) - 1))
    return ordered[low_index], ordered[high_index]


def _buy_hold_return_from_candles(candles: Sequence[dict[str, object]]) -> float:
    if not candles:
        return 0.0
    first = _number(candles[0].get("close"))
    last = _number(candles[-1].get("close"))
    return (last / first - 1) * 100 if first else 0.0


def _signal_index(trade: dict[str, object]) -> int:
    value = trade.get("signal_index")
    return value if isinstance(value, int) else -1


def _trade_index(trade: dict[str, object]) -> int:
    value = trade.get("entry_index")
    return value if isinstance(value, int) else -1


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


def _uses_partial(variant: str) -> bool:
    return variant in {"V4", "V6"}


def _validate_dataset_identities(datasets: Sequence[Dataset]) -> None:
    names = [dataset.name for dataset in datasets]
    if len(names) != len(set(names)):
        raise ValueError("duplicate dataset identity")


def _validate_dataset(dataset: Dataset) -> None:
    if not dataset.candles:
        raise ValueError(f"dataset {dataset.name} is empty")
    if dataset.gaps or dataset.duplicates or dataset.invalid_rows:
        raise ValueError(f"dataset {dataset.name} failed history validation")
    timestamps = [candle.get("timestamp") for candle in dataset.candles]
    present: list[int] = []
    for value in timestamps:
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("bad timestamps")
        present.append(value)
    if present and len(present) != len(timestamps):
        raise ValueError("missing timestamps")
    if any(left >= right for left, right in itertools.pairwise(present)):
        raise ValueError(f"dataset {dataset.name} timestamps are not strictly increasing")


def _atr(candle: dict[str, object], close: float) -> float:
    value = candle.get("atr14", candle.get("atr"))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    return max(close * 0.01, 0.01)


def _number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise TypeError("expected finite numeric value")
    return float(value)
