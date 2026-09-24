from datetime import UTC, datetime

import pytest

from bananatrade.agents.schemas import AnalysisReport, Evidence, Invalidation, KeyLevels
from bananatrade.agents.validator import EvidenceMismatchError, validate_report

SNAPSHOT = {"s": 95.0, "r": 105.0, "i": 95.0, "timeframes": {"1h": {"last_price": 100.0}}}


MISSING = object()


def make(bias="LONG", support=None, resistance=None, invalidation=MISSING, evidence=None, condition="below support"):
    if invalidation is MISSING:
        invalidation = Invalidation(level=95, condition=condition)
    return AnalysisReport(agent="technical_analyst", symbol="BTC/USDT", as_of=datetime.now(UTC), bias=bias, thesis="trend aligned", key_levels=KeyLevels(support=support or [95], resistance=resistance or [105]), invalidation=invalidation, confidence=.7, evidence=evidence or [Evidence(field="s", value=95), Evidence(field="r", value=105), Evidence(field="i", value=95)], data_missing=[])


def test_levels_matching_evidence_pass() -> None:
    assert validate_report(make(evidence=[Evidence(field="s", value=95), Evidence(field="r", value=105)]), SNAPSHOT)


def test_levels_missing_evidence_rejected() -> None:
    with pytest.raises(EvidenceMismatchError, match="support"):
        validate_report(make(support=[94]), SNAPSHOT)

@pytest.mark.parametrize("levels", [([105], [110]), ([90], [95])])
def test_support_resistance_side_rejected(levels) -> None:
    with pytest.raises(EvidenceMismatchError):
        validate_report(make(support=levels[0], resistance=levels[1], evidence=[Evidence(field="a", value=levels[0][0]), Evidence(field="b", value=levels[1][0])]), SNAPSHOT)

@pytest.mark.parametrize("bias, level", [("LONG", 105), ("SHORT", 95)])
def test_invalidation_wrong_side_rejected(bias, level) -> None:
    with pytest.raises(EvidenceMismatchError, match="invalidation"):
        validate_report(make(bias=bias, invalidation=Invalidation(level=level, condition="valid"), evidence=[Evidence(field="a", value=95), Evidence(field="b", value=105)]), SNAPSHOT)


def test_neutral_null_invalidation_passes() -> None:
    assert validate_report(make(bias="NEUTRAL", invalidation=None), SNAPSHOT)

@pytest.mark.parametrize("bias", ["LONG", "SHORT"])
def test_directional_null_invalidation_rejected(bias) -> None:
    with pytest.raises(EvidenceMismatchError, match="invalidation"):
        validate_report(make(bias=bias, invalidation=None), SNAPSHOT)


def test_invalidation_condition_numbers_rejected() -> None:
    with pytest.raises(EvidenceMismatchError, match="condition"):
        validate_report(make(condition="below 95"), SNAPSHOT)

@pytest.mark.parametrize("level", [0, -1, 1, 200])
def test_levels_positive_and_within_fifty_percent(level) -> None:
    with pytest.raises(EvidenceMismatchError):
        validate_report(make(support=[level], evidence=[Evidence(field="x", value=level), Evidence(field="r", value=105)]), SNAPSHOT)
