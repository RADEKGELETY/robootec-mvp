from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from .strategy_registry import GlobalRiskConfig


@dataclass
class StrategyRiskState:
    daily_loss_pct: float = 0.0
    weekly_drawdown_pct: float = 0.0
    consecutive_losses: int = 0
    cooldown_until: Optional[datetime] = None


@dataclass
class PortfolioRiskState:
    daily_loss_pct: float = 0.0


class RiskEngine:
    def __init__(self, config: GlobalRiskConfig) -> None:
        self._config = config
        self._strategy_states: Dict[str, StrategyRiskState] = {}
        self._portfolio_state = PortfolioRiskState()

    def get_strategy_state(self, strategy_id: str) -> StrategyRiskState:
        if strategy_id not in self._strategy_states:
            self._strategy_states[strategy_id] = StrategyRiskState()
        return self._strategy_states[strategy_id]

    def get_portfolio_state(self) -> PortfolioRiskState:
        return self._portfolio_state

    def set_strategy_state(self, strategy_id: str, state: StrategyRiskState) -> None:
        self._strategy_states[strategy_id] = state

    def record_trade_result(self, strategy_id: str, pnl_pct: float, timestamp: datetime) -> None:
        state = self.get_strategy_state(strategy_id)
        if pnl_pct < 0:
            state.daily_loss_pct += abs(pnl_pct)
            state.weekly_drawdown_pct += abs(pnl_pct)
            state.consecutive_losses += 1
        else:
            state.consecutive_losses = 0

        if state.consecutive_losses >= self._config.cooldown_after_losses:
            state.cooldown_until = timestamp + timedelta(
                minutes=self._config.cooldown_duration_minutes
            )

    def record_portfolio_day_loss(self, pnl_pct: float) -> None:
        if pnl_pct < 0:
            self._portfolio_state.daily_loss_pct += abs(pnl_pct)

    def is_in_cooldown(self, strategy_id: str, timestamp: datetime) -> bool:
        state = self.get_strategy_state(strategy_id)
        return state.cooldown_until is not None and timestamp < state.cooldown_until

    def is_risk_breached(self, strategy_id: str) -> bool:
        state = self.get_strategy_state(strategy_id)
        if state.daily_loss_pct >= self._config.max_daily_loss_per_strategy_pct:
            return True
        if state.weekly_drawdown_pct >= self._config.max_weekly_drawdown_per_strategy_pct:
            return True
        if state.consecutive_losses >= self._config.max_consecutive_losses_before_cooldown:
            return True
        if self._portfolio_state.daily_loss_pct >= self._config.max_portfolio_daily_loss_pct:
            return True
        return False
