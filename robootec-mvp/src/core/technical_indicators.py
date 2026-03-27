from __future__ import annotations

from typing import List, Optional

from .market_state_engine import Candle


def sma(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_value = sum(values[:period]) / period
    for value in values[period:]:
        ema_value = (value - ema_value) * k + ema_value
    return ema_value


def vwap(candles: List[Candle]) -> Optional[float]:
    if not candles:
        return None
    total_value = 0.0
    total_volume = 0.0
    for candle in candles:
        typical = (candle.high + candle.low + candle.close) / 3
        total_value += typical * candle.volume
        total_volume += candle.volume
    if total_volume == 0:
        return None
    return total_value / total_volume


def true_range(current: Candle, previous: Optional[Candle]) -> float:
    if previous is None:
        return current.high - current.low
    return max(
        current.high - current.low,
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )


def atr(candles: List[Candle], period: int) -> Optional[float]:
    if period <= 0 or len(candles) < period:
        return None
    ranges = []
    for idx, candle in enumerate(candles[-period:]):
        prev = candles[-period + idx - 1] if idx > 0 else None
        ranges.append(true_range(candle, prev))
    return sum(ranges) / period


def highest_high(candles: List[Candle], lookback: int) -> Optional[float]:
    if lookback <= 0 or len(candles) < lookback:
        return None
    return max(candle.high for candle in candles[-lookback:])


def lowest_low(candles: List[Candle], lookback: int) -> Optional[float]:
    if lookback <= 0 or len(candles) < lookback:
        return None
    return min(candle.low for candle in candles[-lookback:])


def last_close(candles: List[Candle]) -> Optional[float]:
    if not candles:
        return None
    return candles[-1].close


def average_volume(candles: List[Candle], lookback: int) -> Optional[float]:
    if lookback <= 0 or len(candles) < lookback:
        return None
    return sum(candle.volume for candle in candles[-lookback:]) / lookback
