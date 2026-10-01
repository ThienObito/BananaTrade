from __future__ import annotations

import math
from pathlib import Path

import pytest

from bananatrade.brain import Brain
from bananatrade.engine.ensemble_signal import EnsembleSignal, SignalScore
from bananatrade.engine.entry_filter import (
    FEATURE_NAMES,
    EntryFilterConfig,
    FilterVerdict,
    OnnxEntryFilter,
    compute_features,
)

ROOT = Path(__file__).resolve().parents[1]


def candles(count: int = 100, drift: float = 0.4) -> list[dict[str, object]]:
    return [
        {"timestamp": i, "open": 100 + i * drift, "high": 101 + i * drift, "low": 99 + i * drift, "close": 100.5 + i * drift}
        for i in range(count)
    ]


def test_features_shape_side_and_insufficient_data() -> None:
    long = compute_features(candles(), "LONG")
    short = compute_features(candles(), "SHORT")
    assert long is not None and short is not None
    assert len(long) == len(FEATURE_NAMES)
    assert long[-1] == 1.0 and short[-1] == -1.0
    assert all(math.isfinite(v) for v in long)
    assert compute_features(candles(10), "LONG") is None
    assert compute_features(candles(), "NEUTRAL") is None  # type: ignore[arg-type]


def test_features_use_only_trailing_window() -> None:
    data = candles(300)
    assert compute_features(data, "LONG") == compute_features(data[-96:], "LONG")


def test_repo_config_keeps_filter_disabled() -> None:
    config = EntryFilterConfig.from_yaml(ROOT / "config" / "risk.yaml")
    assert config.enabled is False
    assert OnnxEntryFilter.from_config(config, ROOT) is None


def test_config_missing_section_and_validation(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text("max_daily_loss_pct: 0.03\n", encoding="utf-8")
    assert EntryFilterConfig.from_yaml(path) == EntryFilterConfig()
    path.write_text("entry_filter:\n  enabled: true\n  threshold: 1.5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        EntryFilterConfig.from_yaml(path)
    path.write_text("entry_filter:\n  enabled: 'yes'\n", encoding="utf-8")
    with pytest.raises(TypeError):
        EntryFilterConfig.from_yaml(path)


def test_enabled_with_missing_model_fails_closed(tmp_path: Path) -> None:
    gate = OnnxEntryFilter(tmp_path / "missing.onnx", 0.5)
    verdict = gate.evaluate(candles(), "LONG")
    assert not verdict.allowed
    assert "vetoed" in verdict.reason


def test_real_onnx_model_parity_and_threshold(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    skl2onnx = pytest.importorskip("skl2onnx")
    from skl2onnx.common.data_types import FloatTensorType
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, len(FEATURE_NAMES))).astype(np.float32)
    y = (x[:, 0] < 0).astype(int)  # high RSI -> low P(win): the monotonic fixture (RSI 100) is vetoed
    model = LogisticRegression().fit(x, y)
    onx = skl2onnx.convert_sklearn(
        model,
        initial_types=[("input", FloatTensorType([None, len(FEATURE_NAMES)]))],
        options={id(model): {"zipmap": False}},
    )
    path = tmp_path / "m.onnx"
    path.write_bytes(onx.SerializeToString())
    gate = OnnxEntryFilter(path, 0.5)
    for row in x[:20]:
        assert gate.probability(row.tolist()) == pytest.approx(model.predict_proba([row])[0, 1], abs=1e-5)
    assert OnnxEntryFilter(path, 0.5).evaluate(candles(), "LONG").allowed is False
    assert OnnxEntryFilter(path, 0.0).evaluate(candles(), "LONG").allowed is True


class LongEnsemble(EnsembleSignal):
    def score(self, candles: list[dict[str, object]]) -> SignalScore:
        return SignalScore("LONG", 0.95, {"ma_cross_score": 1.0})


class StubFilter:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls = 0

    def evaluate(self, candles: object, side: str) -> FilterVerdict:
        self.calls += 1
        return FilterVerdict(self.allowed, 0.3 if not self.allowed else 0.9, "entry filter prob 0.3000 below threshold 0.5500")


def _spec() -> dict[str, object]:
    return {"name": "X", "digits": 2, "volume_min": 0.01, "volume_step": 0.01, "volume_max": 1.0, "spread": 0.1}


def _account() -> dict[str, object]:
    return {"equity": 10_000.0, "daily_pnl": 0.0, "open_count": 0, "ask": 140.0, "bid": 139.9}


def test_brain_filter_veto_forces_none(tmp_path: Path) -> None:
    stub = StubFilter(False)
    brain = Brain(ensemble=LongEnsemble(), entry_filter=stub, decision_log_path=tmp_path / "d.csv")  # type: ignore[arg-type]
    decision = brain.decide(candles(), _spec(), _account())
    assert decision.side == "NONE"
    assert stub.calls == 1
    assert decision.reasons == ["entry filter prob 0.3000 below threshold 0.5500"]


def test_brain_without_filter_is_unchanged(tmp_path: Path) -> None:
    plain = Brain(ensemble=LongEnsemble(), decision_log_path=tmp_path / "a.csv").decide(candles(), _spec(), _account())
    passing = StubFilter(True)
    gated = Brain(ensemble=LongEnsemble(), entry_filter=passing, decision_log_path=tmp_path / "b.csv").decide(  # type: ignore[arg-type]
        candles(), _spec(), _account()
    )
    assert passing.calls == 1
    assert gated.as_dict() == plain.as_dict()
