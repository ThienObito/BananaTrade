"""Loading and representation of risk limits."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float = 0.10
    max_total_exposure_pct: float = 0.50
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.15
    min_reward_risk: float = 2.0
    max_trades_per_day: int = 5
    cooldown_after_losses: int = 3
    cooldown_minutes: float = 60.0
    require_stop_loss: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RiskLimits":
        cooldown = data.get("cooldown_after_losses", data.get("cooldown_losses", 3))
        if isinstance(cooldown, dict):
            count = cooldown.get("count", 3)
            minutes = cooldown.get("minutes", 60)
        else:
            count, minutes = cooldown, data.get("cooldown_minutes", 60)
        return cls(
            max_position_pct=float(data.get("max_position_pct", cls.max_position_pct)),
            max_total_exposure_pct=float(data.get("max_total_exposure_pct", cls.max_total_exposure_pct)),
            max_daily_loss_pct=float(data.get("max_daily_loss_pct", cls.max_daily_loss_pct)),
            max_drawdown_pct=float(data.get("max_drawdown_pct", cls.max_drawdown_pct)),
            min_reward_risk=float(data.get("min_reward_risk", cls.min_reward_risk)),
            max_trades_per_day=int(data.get("max_trades_per_day", cls.max_trades_per_day)),
            cooldown_after_losses=int(count), cooldown_minutes=float(minutes),
            require_stop_loss=bool(data.get("require_stop_loss", cls.require_stop_loss)),
        )


def load_limits(path: str | Path = "config/risk.yaml") -> RiskLimits:
    with Path(path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return RiskLimits.from_mapping(raw)
