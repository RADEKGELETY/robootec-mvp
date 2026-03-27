from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TradeResult:
    pnl_r: float
    pnl_pct: float


@dataclass(frozen=True)
class PerformanceSummary:
    trades: int
    win_rate: float
    avg_r: float
    profit_factor: float


class PerformanceEvaluator:
    def evaluate(self, trades: List[TradeResult]) -> PerformanceSummary:
        if not trades:
            return PerformanceSummary(trades=0, win_rate=0.0, avg_r=0.0, profit_factor=0.0)

        wins = [t for t in trades if t.pnl_r > 0]
        losses = [t for t in trades if t.pnl_r < 0]
        win_rate = len(wins) / len(trades)
        avg_r = sum(t.pnl_r for t in trades) / len(trades)
        gross_profit = sum(t.pnl_r for t in wins)
        gross_loss = abs(sum(t.pnl_r for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        return PerformanceSummary(
            trades=len(trades),
            win_rate=win_rate,
            avg_r=avg_r,
            profit_factor=profit_factor,
        )
