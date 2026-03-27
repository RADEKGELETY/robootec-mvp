from __future__ import annotations

from dataclasses import dataclass
from .position_sizer import PositionSize
from .signal_engine import Signal
from .strategy_registry import StrategyConfig, TradeManagementConfig


@dataclass(frozen=True)
class ExecutionPlan:
    strategy_id: str
    instrument: str
    direction: str
    order_type: str
    notional_risk: float
    stop_loss_r: float
    take_profit_r: float
    break_even_at_r: float
    partial_exit_at_r: float
    partial_exit_close_pct: float
    trailing_stop_enabled: bool


class ExecutionPolicy:
    def build_plan(
        self,
        strategy: StrategyConfig,
        signal: Signal,
        trade_management: TradeManagementConfig,
        position_size: PositionSize,
    ) -> ExecutionPlan:
        trailing = strategy.type in trade_management.trailing_stop_enabled_for_types
        target_r = float(strategy.exit.get("target_r", 2.0))
        return ExecutionPlan(
            strategy_id=strategy.id,
            instrument=strategy.instrument,
            direction=signal.direction.value,
            order_type="market",
            notional_risk=position_size.notional_risk,
            stop_loss_r=1.0,
            take_profit_r=target_r,
            break_even_at_r=trade_management.break_even_at_r,
            partial_exit_at_r=trade_management.partial_exit_at_r,
            partial_exit_close_pct=trade_management.partial_exit_close_pct,
            trailing_stop_enabled=trailing,
        )
