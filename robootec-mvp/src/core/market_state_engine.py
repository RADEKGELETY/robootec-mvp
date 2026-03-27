from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .strategy_registry import StrategyConfig


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketState:
    timestamp: datetime
    prices: Dict[str, float]
    volatility: Dict[str, float]
    liquidity: Dict[str, float]
    candles: Dict[str, Dict[str, List[Candle]]]
    features: Dict[str, Dict[str, float]]


def _parse_hours(hours: str) -> Tuple[time, time]:
    start_str, end_str = hours.split("-")
    start_parts = [int(part) for part in start_str.split(":")]
    end_parts = [int(part) for part in end_str.split(":")]
    return time(start_parts[0], start_parts[1]), time(end_parts[0], end_parts[1])


class MarketStateEngine:
    def build_state(
        self,
        timestamp: datetime,
        prices: Optional[Dict[str, float]] = None,
        volatility: Optional[Dict[str, float]] = None,
        liquidity: Optional[Dict[str, float]] = None,
        candles: Optional[Dict[str, Dict[str, List[Candle]]]] = None,
        features: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> MarketState:
        return MarketState(
            timestamp=timestamp,
            prices=prices or {},
            volatility=volatility or {},
            liquidity=liquidity or {},
            candles=candles or {},
            features=features or {},
        )

    def get_candles(
        self, market_state: MarketState, instrument: str, timeframe: str
    ) -> List[Candle]:
        return list(market_state.candles.get(instrument, {}).get(timeframe, []))

    def is_strategy_in_session(self, strategy: StrategyConfig, timestamp: datetime) -> bool:
        tz = ZoneInfo(strategy.session_timezone)
        local_time = timestamp.astimezone(tz).time()
        start, end = _parse_hours(strategy.session_hours)
        if start <= end:
            return start <= local_time <= end
        return local_time >= start or local_time <= end
