"""Deterministic pre-trade risk checks driven by config/risk.yaml."""
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RiskConfig:
    max_position_pct: float = 0.10
    max_total_exposure_pct: float = 0.50
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.15
    min_reward_risk: float = 2.0
    max_trades_per_day: int = 5
    cooldown_losses: int = 3

    @classmethod
    def from_yaml(cls, path: str | Path = "config/risk.yaml") -> "RiskConfig":
        data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class RiskDecision:
    """The result of a risk check, including calculated trade distances."""

    approved: bool
    reason: str = "approved"
    reward: float | None = None
    risk: float | None = None
    reward_risk: float | None = None


class RiskEngine:
    def __init__(
        self,
        config: RiskConfig | None = None,
        config_path: str | Path = "config/risk.yaml",
    ) -> None:
        self.config = config or RiskConfig.from_yaml(config_path)

    def check(
        self,
        *,
        equity: float,
        position_notional: float,
        total_exposure: float,
        daily_pnl: float = 0.0,
        peak_equity: float | None = None,
        trades_today: int = 0,
        consecutive_losses: int = 0,
        reward: float | None = None,
        risk: float | None = None,
        entry: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        side: str | None = None,
        kill_switch: bool = False,
    ) -> RiskDecision:
        """Evaluate account limits and, when supplied, a directional proposal.

        The three price fields are an all-or-nothing proposal.  A risk-only check
        may omit all three fields, which keeps broker account-limit checks useful.
        When prices are supplied, this method validates their direction before any
        reward/risk arithmetic and calculates those values from the prices rather
        than trusting caller-provided derived values.
        """
        if kill_switch:
            return RiskDecision(False, "kill switch active")

        proposal = (("entry", entry), ("stop_loss", stop_loss), ("take_profit", take_profit))
        missing = [name for name, value in proposal if value is None]
        has_proposal = len(missing) < len(proposal)
        if has_proposal and missing:
            return RiskDecision(False, f"missing proposal field: {', '.join(missing)}")
        if not has_proposal and (reward is not None or risk is not None):
            return RiskDecision(False, "missing proposal field: entry, stop_loss, take_profit")
        if (reward is None) != (risk is None):
            return RiskDecision(False, "reward and risk must be provided together")

        account_values = (
            ("equity", equity),
            ("position_notional", position_notional),
            ("total_exposure", total_exposure),
            ("daily_pnl", daily_pnl),
        )
        for name, value in account_values:
            if not _finite_number(value):
                return RiskDecision(False, f"{name} must be a finite number")
        if peak_equity is not None and not _finite_number(peak_equity):
            return RiskDecision(False, "peak_equity must be a finite number")

        calculated_reward: float | None = None
        calculated_risk: float | None = None
        calculated_reward_risk: float | None = None
        if has_proposal:
            assert entry is not None
            assert stop_loss is not None
            assert take_profit is not None
            numeric_values = (
                ("entry", entry),
                ("stop_loss", stop_loss),
                ("take_profit", take_profit),
            )
            for name, value in numeric_values:
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
                    return RiskDecision(False, f"{name} must be a finite number")

            try:
                normalized_side = _normalise_side(side, position_notional)
            except (AttributeError, ValueError):
                return RiskDecision(False, "side must be long, short, buy, or sell")
            if normalized_side == "long":
                if stop_loss >= entry:
                    return RiskDecision(False, "long stop_loss must be below entry")
                if take_profit <= entry:
                    return RiskDecision(False, "long take_profit must be above entry")
                calculated_risk = entry - stop_loss
                calculated_reward = take_profit - entry
            else:
                if stop_loss <= entry:
                    return RiskDecision(False, "short stop_loss must be above entry")
                if take_profit >= entry:
                    return RiskDecision(False, "short take_profit must be below entry")
                calculated_risk = stop_loss - entry
                calculated_reward = entry - take_profit
            calculated_reward_risk = calculated_reward / calculated_risk
        c = self.config
        if equity <= 0:
            return RiskDecision(False, "non-positive equity")
        checks = (
            (abs(position_notional) / equity > c.max_position_pct, "max position exceeded"),
            (abs(total_exposure) / equity > c.max_total_exposure_pct, "max total exposure exceeded"),
            (daily_pnl / equity < -c.max_daily_loss_pct, "daily loss limit exceeded"),
            (
                peak_equity is not None
                and peak_equity > 0
                and (peak_equity - equity) / peak_equity > c.max_drawdown_pct,
                "max drawdown exceeded",
            ),
            (trades_today >= c.max_trades_per_day, "daily trade limit exceeded"),
            (consecutive_losses >= c.cooldown_losses, "loss cooldown active"),
        )
        for failed, reason in checks:
            if failed:
                return RiskDecision(
                    False,
                    reason,
                    reward=calculated_reward,
                    risk=calculated_risk,
                    reward_risk=calculated_reward_risk,
                )

        if has_proposal:
            assert calculated_reward is not None
            assert calculated_risk is not None
            assert calculated_reward_risk is not None
            if calculated_risk <= 0 or calculated_reward_risk < c.min_reward_risk:
                return RiskDecision(
                    False,
                    "minimum reward/risk not met",
                    reward=calculated_reward,
                    risk=calculated_risk,
                    reward_risk=calculated_reward_risk,
                )
            return RiskDecision(
                True,
                reward=calculated_reward,
                risk=calculated_risk,
                reward_risk=calculated_reward_risk,
            )

        if reward is not None and risk is not None:
            if not _finite_number(reward) or not _finite_number(risk):
                return RiskDecision(False, "reward and risk must be finite numbers")
            if risk <= 0 or reward / risk < c.min_reward_risk:
                return RiskDecision(False, "minimum reward/risk not met", reward=reward, risk=risk)
            return RiskDecision(True, reward=reward, risk=risk, reward_risk=reward / risk)
        return RiskDecision(True)

    def approve(self, **kwargs: Any) -> None:
        decision = self.check(**kwargs)
        if not decision.approved:
            raise RiskRejected(decision.reason)


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _normalise_side(side: str | None, position_notional: float) -> str:
    if side is None:
        return "short" if position_notional < 0 else "long"
    normalized = side.strip().lower()
    if normalized in {"long", "buy"}:
        return "long"
    if normalized in {"short", "sell"}:
        return "short"
    raise ValueError("side must be long, short, buy, or sell")


class RiskRejected(ValueError):
    pass
