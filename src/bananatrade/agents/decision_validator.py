"""Validation rules for trade proposals against a market snapshot."""
from typing import Any

from .decision_schemas import TradeProposal
from .validator import EvidenceMismatchError


def validate_trade_proposal(
    proposal: TradeProposal, snapshot: dict[str, Any], max_size_pct: float
) -> TradeProposal:
    """Validate prices and sizing using the one-hour snapshot and proposal evidence."""
    bad: list[str] = []
    last_price = snapshot.get("timeframes", {}).get("1h", {}).get("last_price")
    if proposal.side == "HOLD":
        if any(v is not None for v in (proposal.entry, proposal.stop_loss, proposal.take_profit)):
            bad.append("prices")
    elif not isinstance(last_price, (int, float)) or proposal.entry is None:
        bad.append("entry")
    elif abs(proposal.entry - last_price) > abs(last_price) * 0.01:
        bad.append("entry")

    evidence_values = [item.value for item in proposal.evidence]
    for field in ("stop_loss", "take_profit"):
        value = getattr(proposal, field)
        if proposal.side != "HOLD":
            if value is None or not any(abs(value - ev) <= 1e-4 * max(abs(ev), 1.0) for ev in evidence_values):
                bad.append(field)
    if proposal.side == "LONG" and proposal.stop_loss is not None and proposal.take_profit is not None:
        if proposal.stop_loss >= proposal.entry or proposal.take_profit <= proposal.entry:
            bad.extend(["stop_loss", "take_profit"])
    if proposal.side == "SHORT" and proposal.stop_loss is not None and proposal.take_profit is not None:
        if proposal.stop_loss <= proposal.entry or proposal.take_profit >= proposal.entry:
            bad.extend(["stop_loss", "take_profit"])
    if proposal.size_pct > max_size_pct:
        bad.append("size_pct")
    if bad:
        raise EvidenceMismatchError(sorted(set(bad)))
    return proposal


validate_decision = validate_trade_proposal
