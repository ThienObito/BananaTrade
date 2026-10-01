"""Focused tests for deterministic proposal validation and risk limits."""

from typing import Literal, TypedDict

import pytest

from bananatrade.risk import RiskConfig, RiskEngine


class Proposal(TypedDict):
    equity: float
    position_notional: float
    total_exposure: float
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    side: Literal["long", "short"]


@pytest.fixture()
def engine() -> RiskEngine:
    return RiskEngine(RiskConfig(max_position_pct=0.20, min_reward_risk=2.0))


def _proposal() -> Proposal:
    return {
        "equity": 1_000.0,
        "position_notional": 100.0,
        "total_exposure": 100.0,
        "entry": 100.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "side": "long",
    }


def test_missing_entry_is_rejected_before_reward_risk_arithmetic(
    engine: RiskEngine,
) -> None:
    proposal = _proposal()
    proposal["entry"] = None

    decision = engine.check(**proposal, reward=20.0, risk=10.0)

    assert not decision.approved
    assert decision.reason == "missing proposal field: entry"


def test_missing_stop_loss_is_rejected_before_reward_risk_arithmetic(
    engine: RiskEngine,
) -> None:
    proposal = _proposal()
    proposal["stop_loss"] = None

    decision = engine.check(**proposal, reward=20.0, risk=10.0)

    assert not decision.approved
    assert decision.reason == "missing proposal field: stop_loss"


def test_missing_take_profit_is_rejected_before_reward_risk_arithmetic(
    engine: RiskEngine,
) -> None:
    proposal = _proposal()
    proposal["take_profit"] = None

    decision = engine.check(**proposal, reward=20.0, risk=10.0)

    assert not decision.approved
    assert decision.reason == "missing proposal field: take_profit"


def test_valid_long_proposal_reports_correct_reward_risk(engine: RiskEngine) -> None:
    decision = engine.check(**_proposal())

    assert decision.approved
    assert decision.reward == pytest.approx(20.0)
    assert decision.risk == pytest.approx(10.0)
    assert decision.reward_risk == pytest.approx(2.0)


def test_valid_short_proposal_reports_correct_reward_risk(engine: RiskEngine) -> None:
    proposal = _proposal()
    proposal["position_notional"] = -100.0
    proposal["entry"] = 100.0
    proposal["stop_loss"] = 110.0
    proposal["take_profit"] = 80.0
    proposal["side"] = "short"

    decision = engine.check(**proposal)

    assert decision.approved
    assert decision.reward == pytest.approx(20.0)
    assert decision.risk == pytest.approx(10.0)
    assert decision.reward_risk == pytest.approx(2.0)


def test_wrong_side_stop_is_rejected(engine: RiskEngine) -> None:
    proposal = _proposal()
    proposal["stop_loss"] = 110.0

    decision = engine.check(**proposal)

    assert not decision.approved
    assert decision.reason == "long stop_loss must be below entry"


def test_wrong_side_target_is_rejected(engine: RiskEngine) -> None:
    proposal = _proposal()
    proposal["take_profit"] = 90.0

    decision = engine.check(**proposal)

    assert not decision.approved
    assert decision.reason == "long take_profit must be above entry"


def test_kill_switch_rejects_even_an_otherwise_valid_proposal(engine: RiskEngine) -> None:
    decision = engine.check(**_proposal(), kill_switch=True)

    assert not decision.approved
    assert decision.reason == "kill switch active"


def test_position_size_over_limit_is_rejected(engine: RiskEngine) -> None:
    proposal = _proposal()
    proposal["position_notional"] = 201.0

    decision = engine.check(**proposal)

    assert not decision.approved
    assert decision.reason == "max position exceeded"


def test_risk_only_check_still_enforces_position_limit(engine: RiskEngine) -> None:
    decision = engine.check(
        equity=1_000.0,
        position_notional=201.0,
        total_exposure=100.0,
    )

    assert not decision.approved
    assert decision.reason == "max position exceeded"


def test_reward_and_risk_must_be_provided_together(engine: RiskEngine) -> None:
    decision = engine.check(**_proposal(), reward=20.0)

    assert not decision.approved
    assert decision.reason == "reward and risk must be provided together"


def test_non_finite_equity_is_rejected(engine: RiskEngine) -> None:
    proposal = _proposal()
    proposal["equity"] = float("nan")

    decision = engine.check(**proposal)

    assert not decision.approved
    assert decision.reason == "equity must be a finite number"


def test_all_missing_proposal_fields_are_rejected_when_derived_values_are_given(
    engine: RiskEngine,
) -> None:
    decision = engine.check(
        equity=1_000.0,
        position_notional=100.0,
        total_exposure=100.0,
        reward=20.0,
        risk=10.0,
    )

    assert not decision.approved
    assert decision.reason == "missing proposal field: entry, stop_loss, take_profit"


def test_invalid_side_is_rejected_without_raising(engine: RiskEngine) -> None:
    decision = engine.check(
        equity=1_000.0,
        position_notional=100.0,
        total_exposure=100.0,
        entry=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        side="diagonal",
    )

    assert not decision.approved
    assert decision.reason == "side must be long, short, buy, or sell"
