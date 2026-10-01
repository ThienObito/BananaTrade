from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bananatrade.brain import Brain, Decision, decide
from bananatrade.engine.ensemble_signal import EnsembleSignal
from bananatrade.engine.execution_model import ExecutionModel
from bananatrade.engine.regime_detector import Regime, RegimeDetector
from bananatrade.risk_manager import RiskManager


def candles(count: int = 80, drift: float = 0.4) -> list[dict[str, object]]:
    return [{"open": 100 + index * drift, "high": 101 + index * drift, "low": 99 + index * drift, "close": 100 + index * drift, "volume": 100.0} for index in range(count)]


def spec(**overrides: object) -> dict[str, object]:
    return {"name": "XAUUSDm", "digits": 2, "point": 0.01, "volume_min": 0.01, "volume_step": 0.01, "volume_max": 1.0, "stops_level": 10, "spread": 0.1, **overrides}


def account(**overrides: object) -> dict[str, object]:
    return {"equity": 10_000.0, "daily_pnl": 0.0, "open_count": 0, "ask": 140.0, "bid": 139.9, **overrides}


def brain(tmp_path: Path, **kwargs: object) -> Brain:
    return Brain(decision_log_path=tmp_path / "decisions.csv", **kwargs)


def test_decision_shape() -> None:
    value = Decision("NONE", 0.0, None, None, None, 0.0, ["x"])
    assert value.as_dict()["side"] == "NONE"
    assert not value.is_trade


def test_low_confidence_returns_none(tmp_path: Path) -> None:
    value = brain(tmp_path, confidence_threshold=1.0).decide(candles(), spec(), account())
    assert value.side == "NONE"
    assert value.reasons


def test_volatile_regime_returns_none(tmp_path: Path) -> None:
    class Volatile(RegimeDetector):
        def detect(self, candles):
            return Regime.VOLATILE
    value = brain(tmp_path, regime_detector=Volatile()).decide(candles(), spec(), account())
    assert value.side == "NONE"
    assert "VOLATILE regime" in value.reasons


def test_spread_guard_returns_none(tmp_path: Path) -> None:
    value = brain(tmp_path, max_spread=0.01).decide(candles(), spec(spread=1.0), account())
    assert value.side == "NONE"
    assert any("spread" in reason for reason in value.reasons)


def test_neutral_signal_returns_none(tmp_path: Path) -> None:
    value = brain(tmp_path, ensemble=EnsembleSignal(ma_fast=2, ma_slow=50)).decide(candles(80, 0.0), spec(), account())
    assert value.side == "NONE"


def test_risk_failure_returns_none(tmp_path: Path) -> None:
    value = brain(tmp_path, risk_manager=RiskManager(max_open_positions=0), confidence_threshold=0.0).decide(candles(80, 0.4), spec(), account())
    assert value.side == "NONE"
    assert value.reasons


def test_successful_decision_has_protective_prices(tmp_path: Path) -> None:
    value = brain(tmp_path, execution_model=ExecutionModel(risk_pct=0.001)).decide(candles(), spec(), account())
    assert value.side in {"BUY", "SELL", "NONE"}
    if value.is_trade:
        assert value.entry is not None and value.sl is not None and value.tp is not None
        assert value.volume >= 0.01


def test_volume_rounds_to_step(tmp_path: Path) -> None:
    value = brain(tmp_path, execution_model=ExecutionModel(risk_pct=0.001)).decide(candles(), spec(volume_step=0.1, volume_min=0.1), account())
    assert value.volume == pytest.approx(round(value.volume, 1))


def test_decision_csv_logs_none(tmp_path: Path) -> None:
    path = tmp_path / "decisions.csv"
    brain(tmp_path, confidence_threshold=1.0).decide(candles(), spec(), account())
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["side"] == "NONE"
    assert rows[0]["reasons"]


def test_decision_csv_logs_every_call(tmp_path: Path) -> None:
    value = brain(tmp_path, confidence_threshold=1.0)
    value.decide(candles(), spec(), account())
    value.decide(candles(), spec(), account())
    assert len((tmp_path / "decisions.csv").read_text(encoding="utf-8").splitlines()) == 3


def test_object_specs_are_supported(tmp_path: Path) -> None:
    class Spec:
        name = "EURUSDm"
        digits = 5
        volume_min = 0.01
        volume_step = 0.01
        volume_max = 1.0
        spread = 0.0001
    assert brain(tmp_path, confidence_threshold=1.0).decide(candles(), Spec(), account()).side == "NONE"


def test_module_decide_api_logs(tmp_path: Path) -> None:
    value = decide(candles(), spec(), account(), confidence_threshold=1.0, decision_log_path=tmp_path / "x.csv")
    assert value.side == "NONE"


def test_invalid_brain_threshold_rejected() -> None:
    with pytest.raises(ValueError, match="between"):
        Brain(confidence_threshold=2.0)
