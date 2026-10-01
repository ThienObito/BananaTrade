"""Walk-forward strategy parameter optimization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from statistics import mean
from typing import Protocol

from ..engine.strategy import SignalResult
from .engine import BacktestEngine, BacktestResult


class StrategyInstance(Protocol):
    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        ...


class StrategyFactory(Protocol):
    def __call__(self, **params: object) -> StrategyInstance:
        ...


@dataclass(frozen=True)
class WindowResult:
    """One train/test walk-forward window."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int
    best_params: dict[str, object]
    train_sharpe: float
    test_sharpe: float
    test_result: BacktestResult


@dataclass(frozen=True)
class WalkForwardResult:
    """All windows and aggregate walk-forward metrics."""

    windows: list[WindowResult]
    avg_sharpe: float
    stability_score: float


class WalkForwardOptimizer:
    """Grid-search strategy parameters in rolling train/test windows."""

    def __init__(self, engine: BacktestEngine | None = None) -> None:
        self.engine = engine or BacktestEngine()

    def optimize(
        self,
        candles: list[dict[str, object]],
        strategy_class: type[StrategyInstance] | StrategyFactory,
        param_grid: Mapping[str, list[object]],
        n_splits: int = 5,
    ) -> WalkForwardResult:
        """Optimize each 70/30 window and evaluate selected params out-of-sample."""
        if n_splits <= 0:
            raise ValueError("n_splits must be positive")
        if len(candles) < n_splits * 2:
            raise ValueError("candles too short for requested splits")
        if not param_grid or any(not values for values in param_grid.values()):
            raise ValueError("param_grid must contain non-empty value lists")
        windows: list[WindowResult] = []
        for train_start, train_end, test_start, test_end in self._windows(len(candles), n_splits):
            train = candles[train_start:train_end]
            test = candles[test_start:test_end]
            best_params: dict[str, object] | None = None
            best_train: BacktestResult | None = None
            for params in self._parameter_sets(param_grid):
                result = self.engine.run(train, self._strategy(strategy_class, params))
                if best_train is None or result.sharpe_ratio > best_train.sharpe_ratio:
                    best_params = params
                    best_train = result
            if best_params is None or best_train is None:
                raise RuntimeError("no strategy parameters evaluated")
            test_result = self.engine.run(test, self._strategy(strategy_class, best_params))
            windows.append(
                WindowResult(
                    train_start,
                    train_end,
                    test_start,
                    test_end,
                    best_params,
                    best_train.sharpe_ratio,
                    test_result.sharpe_ratio,
                    test_result,
                )
            )
        test_sharpes = [window.test_sharpe for window in windows]
        avg_sharpe = mean(test_sharpes) if test_sharpes else 0.0
        positive = sum(1 for value in test_sharpes if value > 0)
        stability_score = positive / len(test_sharpes) if test_sharpes else 0.0
        return WalkForwardResult(windows, avg_sharpe, stability_score)

    @staticmethod
    def _windows(length: int, n_splits: int) -> list[tuple[int, int, int, int]]:
        window_size = length // n_splits
        result: list[tuple[int, int, int, int]] = []
        for index in range(n_splits):
            start = index * window_size
            end = length if index == n_splits - 1 else (index + 1) * window_size
            span = end - start
            train_length = max(1, int(span * 0.7))
            train_end = start + train_length
            if train_end >= end:
                train_end = end - 1
            result.append((start, train_end, train_end, end))
        return result

    @staticmethod
    def _parameter_sets(param_grid: Mapping[str, list[object]]) -> list[dict[str, object]]:
        keys = list(param_grid)
        return [dict(zip(keys, values, strict=True)) for values in product(*(param_grid[key] for key in keys))]

    @staticmethod
    def _strategy(strategy_class: type[StrategyInstance] | StrategyFactory, params: dict[str, object]) -> StrategyInstance:
        return strategy_class(**params)
