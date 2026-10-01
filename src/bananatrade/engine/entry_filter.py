"""Optional local ONNX probability filter applied after the ensemble signal.

The filter can only *veto* a trade. It never creates or flips a signal. When it is
disabled (the default) the brain behaves exactly as before. When it is enabled but
the model or ``onnxruntime`` cannot be loaded, every trade is vetoed (fail closed),
because a misconfigured safety gate must not silently let trades through.

Feature definitions live here and are imported by ``scripts/train_entry_filter.py``
so training and inference can never drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml

from ..data.indicators import ema, rsi
from .regime_detector import RegimeDetector

FEATURE_NAMES: tuple[str, ...] = ("rsi14", "ema_diff", "adx14", "body", "side")
# EMA/ADX are recursive; computing on a fixed trailing window keeps train and live identical.
FEATURE_WINDOW = 96
MIN_CANDLES = 60


def compute_features(
    candles: Sequence[Mapping[str, object]], side: Literal["LONG", "SHORT"]
) -> list[float] | None:
    """Return the model feature vector for the latest closed candle, or None if unusable."""
    if side not in ("LONG", "SHORT"):
        return None
    window = list(candles[-FEATURE_WINDOW:])
    if len(window) < MIN_CANDLES:
        return None
    frame = pd.DataFrame(window)
    for column in ("open", "high", "low", "close"):
        if column not in frame:
            return None
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["open", "high", "low", "close"]].isna().any().any() or (frame["close"] <= 0).any():
        return None
    close = frame["close"]
    last = frame.iloc[-1]
    rsi_value = float(rsi(close, 14).iloc[-1])
    ema_diff = float((ema(close, 20).iloc[-1] - ema(close, 50).iloc[-1]) / close.iloc[-1])
    adx_value = RegimeDetector._adx(frame, 14)
    candle_range = float(last["high"] - last["low"])
    body = float(last["close"] - last["open"]) / candle_range if candle_range > 0 else 0.0
    values = [rsi_value, ema_diff, adx_value, body, 1.0 if side == "LONG" else -1.0]
    return values if all(isfinite(v) for v in values) else None


@dataclass(frozen=True)
class EntryFilterConfig:
    """``entry_filter`` section of config/risk.yaml."""

    enabled: bool = False
    model_path: str = "models/entry_filter.onnx"
    threshold: float = 0.55

    @classmethod
    def from_yaml(cls, path: str | Path) -> EntryFilterConfig:
        try:
            data: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            return cls()
        section = data.get("entry_filter") if isinstance(data, dict) else None
        if not isinstance(section, dict):
            return cls()
        enabled = section.get("enabled", False)
        threshold = section.get("threshold", cls.threshold)
        model_path = section.get("model_path", cls.model_path)
        if not isinstance(enabled, bool):
            raise TypeError("entry_filter.enabled must be true or false")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
            raise ValueError("entry_filter.threshold must be a number in [0, 1]")
        if not isinstance(model_path, str) or not model_path:
            raise ValueError("entry_filter.model_path must be a non-empty string")
        return cls(enabled, model_path, float(threshold))


@dataclass(frozen=True)
class FilterVerdict:
    allowed: bool
    probability: float | None
    reason: str


class OnnxEntryFilter:
    """Score P(trade is net-profitable) with a local ONNX classifier."""

    def __init__(self, model_path: str | Path, threshold: float) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        self.model_path = Path(model_path)
        self.threshold = float(threshold)
        self._session: Any = None
        self._input_name = ""
        self._load_error: str | None = None
        try:
            import onnxruntime as ort  # local import keeps the dependency optional

            self._session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
            self._input_name = self._session.get_inputs()[0].name
        except Exception as exc:  # noqa: BLE001 - any load failure must fail closed
            self._load_error = f"{type(exc).__name__}: {exc}"

    @classmethod
    def from_config(cls, config: EntryFilterConfig, root: str | Path = ".") -> OnnxEntryFilter | None:
        """Return None when disabled so callers keep the unfiltered behaviour."""
        if not config.enabled:
            return None
        path = Path(config.model_path)
        if not path.is_absolute():
            path = Path(root) / path
        return cls(path, config.threshold)

    def probability(self, features: Sequence[float]) -> float:
        import numpy as np

        if self._session is None:
            raise RuntimeError(f"entry filter model unavailable ({self._load_error})")
        batch = np.asarray([list(features)], dtype=np.float32)
        outputs = self._session.run(None, {self._input_name: batch})
        # zipmap=False → outputs = [labels, probabilities(n, 2)]; column 1 is P(win).
        proba = outputs[-1]
        value = float(proba[0][1])
        if not isfinite(value):
            raise RuntimeError("entry filter returned a non-finite probability")
        return value

    def evaluate(self, candles: Sequence[Mapping[str, object]], side: Literal["LONG", "SHORT"]) -> FilterVerdict:
        features = compute_features(candles, side)
        if features is None:
            return FilterVerdict(False, None, "entry filter: insufficient or invalid candles for features")
        try:
            prob = self.probability(features)
        except Exception as exc:  # noqa: BLE001 - fail closed
            return FilterVerdict(False, None, f"entry filter error, trade vetoed: {exc}")
        if prob < self.threshold:
            return FilterVerdict(False, prob, f"entry filter prob {prob:.4f} below threshold {self.threshold:.4f}")
        return FilterVerdict(True, prob, f"entry filter prob {prob:.4f} passed")
