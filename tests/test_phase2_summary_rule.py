from datetime import UTC, datetime

import pytest

from bananatrade.agents.schemas import ObservationReport
from bananatrade.agents.validator import EvidenceMismatchError, validate_report

SNAPSHOT = {"timeframes": {"1h": {"last_price": 100}, "4h": {"last_price": 101}}}


def make(summary: str) -> ObservationReport:
    return ObservationReport(agent="x", symbol="BTC/USDT", as_of=datetime.now(UTC), signals=[], confidence=0.5, data_missing=[], summary=summary)


@pytest.mark.parametrize("summary", ["RSI above 70 on 4h, momentum fading on 1h", "1h and 4h trends aligned", "no clear signal"])
def test_summary_allowed(summary: str) -> None:
    assert validate_report(make(summary), SNAPSHOT)


@pytest.mark.parametrize("summary", ["price near 84,008", "funding at 0.01%", "about 84k", "RSI 72.5 on 4h", "volume 3x normal"])
def test_summary_numbers_rejected(summary: str) -> None:
    with pytest.raises(EvidenceMismatchError, match="summary"):
        validate_report(make(summary), SNAPSHOT)
