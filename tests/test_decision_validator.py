import pytest

from bananatrade.agents.decision_schemas import Evidence, TradeProposal
from bananatrade.agents.decision_validator import validate_trade_proposal
from bananatrade.agents.validator import EvidenceMismatchError

SNAPSHOT = {"timeframes": {"1h": {"last_price": 100.0}}}


def proposal(**kwargs):
    values = dict(symbol="BTC/USDT", side="LONG", entry=100.5, stop_loss=95.0,
                  take_profit=110.0, size_pct=5.0, timeframe="1h", thesis="trend aligned",
                  invalidation_condition="close below support", confidence=.8,
                  evidence=[Evidence(field="support", value=95), Evidence(field="target", value=110)])
    values.update(kwargs)
    return TradeProposal(**values)


def test_valid_proposal_passes():
    assert validate_trade_proposal(proposal(), SNAPSHOT, 10) == proposal()


@pytest.mark.parametrize("kwargs", [
    {"entry": 102},
    {"stop_loss": 96},
    {"take_profit": 111},
    {"side": "LONG", "stop_loss": 105},
    {"size_pct": 11},
])
def test_invalid_proposal_rejected(kwargs):
    with pytest.raises(EvidenceMismatchError):
        validate_trade_proposal(proposal(**kwargs), SNAPSHOT, 10)


def test_hold_has_no_prices():
    with pytest.raises(ValueError):
        proposal(side="HOLD", entry=100.0, stop_loss=None, take_profit=None)
