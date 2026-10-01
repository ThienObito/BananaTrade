"""Property and boundary tests for paper-trading safety contracts."""
from __future__ import annotations

from time import monotonic
from typing import Literal, TypedDict

from hypothesis import given
from hypothesis import strategies as st

from bananatrade.paper_broker import PaperBroker
from bananatrade.risk import RiskConfig, RiskEngine


class ProposalIn(TypedDict):
    equity: float
    position_notional: float
    total_exposure: float
    daily_pnl: float
    peak_equity: float
    trades_today: int
    consecutive_losses: int
    entry: float
    stop_loss: float
    take_profit: float
    side: Literal["long", "short"]


@st.composite
def valid_proposals(draw: st.DrawFn) -> ProposalIn:
    equity = float(draw(st.integers(min_value=1_000, max_value=100_000)))
    entry = float(draw(st.integers(min_value=100, max_value=10_000)))
    risk_distance = float(draw(st.integers(min_value=1, max_value=50)))
    reward_distance = risk_distance * float(draw(st.integers(min_value=2, max_value=10)))
    side = draw(st.sampled_from(["long", "short"]))
    if side == "long":
        stop_loss = entry - risk_distance
        take_profit = entry + reward_distance
    else:
        stop_loss = entry + risk_distance
        take_profit = entry - reward_distance
    return {
        "equity": equity,
        "position_notional": float(draw(st.integers(min_value=-50, max_value=50))),
        "total_exposure": float(draw(st.integers(min_value=0, max_value=100))),
        "daily_pnl": float(draw(st.integers(min_value=-10, max_value=10))),
        "peak_equity": equity + float(draw(st.integers(min_value=0, max_value=100))),
        "trades_today": draw(st.integers(min_value=0, max_value=4)),
        "consecutive_losses": draw(st.integers(min_value=0, max_value=2)),
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "side": side,
    }


@given(valid_proposals())
def test_risk_evaluate_never_raises_for_valid_proposal(proposal: ProposalIn) -> None:
    engine = RiskEngine(RiskConfig())

    decision = engine.check(**proposal)

    assert isinstance(decision.approved, bool)


def test_paper_broker_fill_executes_within_two_bars_of_order_time() -> None:
    broker = PaperBroker(10_000.0)
    bar_seconds = 3_600.0
    order_time = monotonic()

    fill = broker.submit_market("BTC/USDT", "BUY", 1.0, 100.0)

    fill_time = monotonic()
    elapsed_bars = (fill_time - order_time) / bar_seconds
    assert fill in broker.fills
    assert elapsed_bars <= 2.0
