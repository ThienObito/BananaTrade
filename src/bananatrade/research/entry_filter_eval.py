"""Backtest adapter for the brain's ensemble signal, optionally gated by the ONNX entry filter.

Used by ``scripts/train_entry_filter.py`` both to generate cost-aware labels (via the
real BacktestEngine fills/fees) and to compare filtered vs unfiltered performance.
"""

from __future__ import annotations

import random
from statistics import mean

from ..engine.ensemble_signal import EnsembleSignal
from ..engine.entry_filter import FEATURE_WINDOW, OnnxEntryFilter, compute_features
from ..engine.strategy import SignalResult


class EnsembleBacktestStrategy:
    """Replicates ``Brain``'s first stage: ``EnsembleSignal.score`` then the optional filter.

    ``EnsembleSignal`` can only be non-NEUTRAL on an MA(20/50) cross bar, so a cheap
    exact cross pre-check skips the pandas work on all other bars.
    """

    lookback = max(FEATURE_WINDOW, 120)

    def __init__(self, entry_filter: OnnxEntryFilter | None = None) -> None:
        self.ensemble = EnsembleSignal()
        self.entry_filter = entry_filter
        # timestamp of signal bar -> feature vector, for label generation
        self.features_by_ts: dict[object, list[float]] = {}
        self.vetoed = 0

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        fast, slow = self.ensemble.ma_fast, self.ensemble.ma_slow
        if len(candles) < slow + 1:
            return SignalResult("NEUTRAL", 0.0, "warmup")
        closes = [float(c["close"]) for c in candles[-(slow + 1):]]  # type: ignore[arg-type]
        pf, ps = mean(closes[-fast - 1:-1]), mean(closes[:-1])
        cf, cs = mean(closes[-fast:]), mean(closes[1:])
        if not ((pf <= ps and cf > cs) or (pf >= ps and cf < cs)):
            return SignalResult("NEUTRAL", 0.0, "no MA cross")
        score = self.ensemble.score(candles)
        if score.bias == "NEUTRAL":
            return SignalResult("NEUTRAL", score.confidence, "ensemble neutral")
        features = compute_features(candles, score.bias)
        if features is not None:
            self.features_by_ts[candles[-1].get("timestamp")] = features
        if self.entry_filter is not None:
            verdict = self.entry_filter.evaluate(candles, score.bias)
            if not verdict.allowed:
                self.vetoed += 1
                return SignalResult("NEUTRAL", score.confidence, verdict.reason)
        return SignalResult(score.bias, score.confidence, "ensemble")


class RandomVetoStrategy(EnsembleBacktestStrategy):
    """Control: vetoes ensemble signals at random with a fixed keep rate.

    A learned filter only shows skill if it beats this at the same trade frequency;
    otherwise any improvement just comes from trading less (lower cost drag).
    """

    def __init__(self, keep_rate: float, seed: int) -> None:
        super().__init__(None)
        if not 0.0 <= keep_rate <= 1.0:
            raise ValueError("keep_rate must be in [0, 1]")
        self.keep_rate = keep_rate
        self.rng = random.Random(seed)

    def generate_signal(self, candles: list[dict[str, object]]) -> SignalResult:
        signal = super().generate_signal(candles)
        if signal.bias != "NEUTRAL" and self.rng.random() >= self.keep_rate:
            self.vetoed += 1
            return SignalResult("NEUTRAL", signal.confidence, "random veto (control)")
        return signal
