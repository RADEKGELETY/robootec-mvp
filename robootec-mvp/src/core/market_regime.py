from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .market_state_engine import Candle
from .technical_indicators import atr, sma


@dataclass(frozen=True)
class MarketRegime:
    label: str
    trend_strength: float
    volatility: float


def evaluate_market_regime(candles: List[Candle]) -> MarketRegime:
    if len(candles) < 50:
        return MarketRegime(label="unknown", trend_strength=0.0, volatility=0.0)

    closes = [candle.close for candle in candles]
    fast = sma(closes, 20)
    slow = sma(closes, 50)
    if fast is None or slow is None or slow == 0:
        trend_strength = 0.0
    else:
        trend_strength = (fast - slow) / slow

    avg_atr = atr(candles, 14)
    volatility = avg_atr / closes[-1] if avg_atr and closes[-1] else 0.0

    if abs(trend_strength) > 0.002:
        label = "trend"
    elif volatility > 0.015:
        label = "volatile"
    else:
        label = "range"

    return MarketRegime(label=label, trend_strength=trend_strength, volatility=volatility)
