from __future__ import annotations

from dataclasses import dataclass
from .strategy_registry import GlobalRiskConfig, StrategyConfig


@dataclass(frozen=True)
class PositionSize:
    risk_pct: float
    size_multiplier: float
    notional_risk: float


class PositionSizer:
    def __init__(self, global_risk: GlobalRiskConfig, capital_per_strategy: float) -> None:
        self._global_risk = global_risk
        self._capital_per_strategy = capital_per_strategy

    def size_position(
        self,
        strategy: StrategyConfig,
        confidence_multiplier: float,
        consecutive_losses: int,
    ) -> PositionSize:
        base_risk_pct = float(strategy.risk.get("max_position_risk_pct", 0.5))
        size_multiplier = confidence_multiplier

        if consecutive_losses >= self._global_risk.loss_streak_after_losses:
            reduction_factor = 1.0 - (self._global_risk.loss_streak_reduction_pct / 100.0)
            size_multiplier *= max(reduction_factor, 0.0)

        risk_pct = base_risk_pct * size_multiplier
        notional_risk = self._capital_per_strategy * (risk_pct / 100.0)
        return PositionSize(
            risk_pct=risk_pct,
            size_multiplier=size_multiplier,
            notional_risk=notional_risk,
        )
