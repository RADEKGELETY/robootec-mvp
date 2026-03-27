from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .market_state_engine import Candle, MarketState
from .strategy_registry import ConfidenceModelConfig, StrategyConfig
from .technical_indicators import (
    atr,
    average_volume,
    highest_high,
    last_close,
    lowest_low,
    sma,
    vwap,
)


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass(frozen=True)
class Signal:
    strategy_id: str
    instrument: str
    direction: SignalDirection
    confidence: float
    timestamp: datetime
    reason: str


@dataclass(frozen=True)
class SignalCandidate:
    direction: SignalDirection
    reason: str
    signal_quality: float
    trend_alignment: float
    volatility_regime: float
    liquidity_score: float
    event_risk: float


class SignalEngine:
    def __init__(self, confidence_model: Optional[ConfidenceModelConfig] = None) -> None:
        self._confidence_model = confidence_model

    def generate_signals(
        self,
        strategies: List[StrategyConfig],
        market_state: MarketState,
        confidence_model: Optional[ConfidenceModelConfig] = None,
    ) -> List[Signal]:
        model = confidence_model or self._confidence_model
        signals: List[Signal] = []

        for strategy in strategies:
            candidate = self._generate_for_strategy(strategy, market_state)
            if candidate is None:
                continue
            confidence = self._compute_confidence(
                strategy, candidate, market_state, model
            )
            signals.append(
                Signal(
                    strategy_id=strategy.id,
                    instrument=strategy.instrument,
                    direction=candidate.direction,
                    confidence=confidence,
                    timestamp=market_state.timestamp,
                    reason=candidate.reason,
                )
            )

        return signals

    def _generate_for_strategy(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        model = str(strategy.entry.get("model", "")).strip().lower()
        if model == "opening_range_breakout":
            return self._orb_momentum(strategy, market_state)
        if model == "vwap_pullback":
            return self._vwap_pullback(strategy, market_state)
        if model == "macro_trend_pullback":
            return self._macro_trend_pullback(strategy, market_state)
        if model == "breakout_retest":
            return self._daily_breakout_retest(strategy, market_state)
        if model == "london_breakout":
            return self._london_breakout(strategy, market_state)
        if strategy.id == "NAS_01_ORB_MOMENTUM":
            return self._orb_momentum(strategy, market_state)
        if strategy.id == "NAS_02_VWAP_PULLBACK":
            return self._vwap_pullback(strategy, market_state)
        if strategy.id == "XAU_02_MACRO_TREND_PULLBACK":
            return self._macro_trend_pullback(strategy, market_state)
        if strategy.id == "BTC_01_DAILY_BREAKOUT_RETEST":
            return self._daily_breakout_retest(strategy, market_state)
        if strategy.id == "FX_01_LONDON_BREAKOUT":
            return self._london_breakout(strategy, market_state)
        return None

    def _orb_momentum(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        candles = self._get_candles(market_state, strategy)
        if len(candles) < 4:
            return None

        tz = ZoneInfo(strategy.session_timezone)
        session_start, _ = _session_window(
            market_state.timestamp, tz, strategy.session_hours
        )
        range_minutes = int(strategy.entry.get("range_minutes", 15))
        range_end = session_start + timedelta(minutes=range_minutes)

        opening_range = [
            candle
            for candle in candles
            if session_start <= candle.timestamp.astimezone(tz) < range_end
        ]
        if not opening_range:
            return None

        range_high = max(candle.high for candle in opening_range)
        range_low = min(candle.low for candle in opening_range)
        last_candle = candles[-1]
        avg_volume = average_volume(opening_range, len(opening_range)) or 0.0
        volume_multiple = float(strategy.entry.get("volume_spike_multiple", 1.5))
        volume_spike = last_candle.volume > avg_volume * volume_multiple if avg_volume > 0 else False
        range_size = max(range_high - range_low, 1e-6)
        min_breakout_r = float(strategy.entry.get("min_breakout_r", 0.0))

        if last_candle.close > range_high and volume_spike:
            breakout_r = (last_candle.close - range_high) / range_size
            if breakout_r < min_breakout_r:
                return None
            quality = min(breakout_r, 1.0)
            return self._candidate(
                SignalDirection.LONG,
                "orb_breakout_long",
                quality,
                trend_alignment=0.8,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        if last_candle.close < range_low and volume_spike:
            breakout_r = (range_low - last_candle.close) / range_size
            if breakout_r < min_breakout_r:
                return None
            quality = min(breakout_r, 1.0)
            return self._candidate(
                SignalDirection.SHORT,
                "orb_breakout_short",
                quality,
                trend_alignment=0.8,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        return None

    def _vwap_pullback(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        candles = self._get_candles(market_state, strategy)
        if len(candles) < 20:
            return None
        vwap_value = vwap(candles)
        if vwap_value is None:
            return None
        closes = [candle.close for candle in candles]
        fast_period = int(strategy.entry.get("fast_ma", 20))
        slow_period = int(strategy.entry.get("slow_ma", 50))
        fast = sma(closes, fast_period)
        slow = sma(closes, slow_period) or sma(closes, max(fast_period + 10, 30))
        if fast is None or slow is None:
            return None
        trend = 1 if fast > slow else -1
        last_candle = candles[-1]
        max_distance_pct = float(strategy.entry.get("max_distance_pct", 0.3)) / 100.0
        distance = abs(last_candle.close - vwap_value) / vwap_value
        if distance > max_distance_pct:
            return None
        if trend > 0 and last_candle.close >= vwap_value:
            quality = max(0.0, 1.0 - distance * 200)
            return self._candidate(
                SignalDirection.LONG,
                "vwap_pullback_long",
                quality,
                trend_alignment=0.9,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        if trend < 0 and last_candle.close <= vwap_value:
            quality = max(0.0, 1.0 - distance * 200)
            return self._candidate(
                SignalDirection.SHORT,
                "vwap_pullback_short",
                quality,
                trend_alignment=0.9,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        return None

    def _macro_trend_pullback(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        candles = self._get_candles(market_state, strategy)
        if len(candles) < 55:
            return None
        closes = [candle.close for candle in candles]
        fast_period = int(strategy.entry.get("fast_ma", 20))
        slow_period = int(strategy.entry.get("slow_ma", 50))
        fast = sma(closes, fast_period)
        slow = sma(closes, slow_period)
        if fast is None or slow is None:
            return None
        last_candle = candles[-1]
        max_pullback_pct = float(strategy.entry.get("max_pullback_pct", 0.5)) / 100.0
        distance = abs(last_candle.close - fast) / fast if fast else 0.0
        if distance > max_pullback_pct:
            return None
        confirm_candle = str(strategy.entry.get("confirm_candle", "directional")).lower()
        long_confirm = last_candle.close > last_candle.open if confirm_candle == "directional" else True
        short_confirm = last_candle.close < last_candle.open if confirm_candle == "directional" else True
        if fast > slow and long_confirm:
            quality = max(0.0, 1.0 - distance * 200)
            return self._candidate(
                SignalDirection.LONG,
                "macro_trend_pullback_long",
                quality,
                trend_alignment=1.0,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        if fast < slow and short_confirm:
            quality = max(0.0, 1.0 - distance * 200)
            return self._candidate(
                SignalDirection.SHORT,
                "macro_trend_pullback_short",
                quality,
                trend_alignment=1.0,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        return None

    def _daily_breakout_retest(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        candles = self._get_candles(market_state, strategy)
        if len(candles) < 22:
            return None
        lookback_bars = int(strategy.entry.get("lookback_bars", 20))
        lookback = candles[-(lookback_bars + 2) : -2]
        breakout_high = highest_high(lookback, len(lookback))
        breakout_low = lowest_low(lookback, len(lookback))
        if breakout_high is None or breakout_low is None:
            return None
        prev_candle = candles[-2]
        last_candle = candles[-1]
        tolerance = float(strategy.entry.get("retest_tolerance_pct", 0.3)) / 100.0

        if prev_candle.close > breakout_high:
            if last_candle.low <= breakout_high * (1 + tolerance) and last_candle.close > breakout_high:
                quality = min((last_candle.close - breakout_high) / breakout_high * 50, 1.0)
                return self._candidate(
                    SignalDirection.LONG,
                    "breakout_retest_long",
                    quality,
                    trend_alignment=0.85,
                    market_state=market_state,
                    instrument=strategy.instrument,
                    candles=candles,
                )
        if prev_candle.close < breakout_low:
            if last_candle.high >= breakout_low * (1 - tolerance) and last_candle.close < breakout_low:
                quality = min((breakout_low - last_candle.close) / breakout_low * 50, 1.0)
                return self._candidate(
                    SignalDirection.SHORT,
                    "breakout_retest_short",
                    quality,
                    trend_alignment=0.85,
                    market_state=market_state,
                    instrument=strategy.instrument,
                    candles=candles,
                )
        return None

    def _london_breakout(
        self, strategy: StrategyConfig, market_state: MarketState
    ) -> Optional[SignalCandidate]:
        candles = self._get_candles(market_state, strategy)
        if len(candles) < 20:
            return None

        tz = ZoneInfo("Europe/London")
        asian_session = str(strategy.entry.get("asian_session", "00:00-07:00"))
        asian_start, asian_end = _parse_hours(asian_session)
        asian_range = [
            candle
            for candle in candles
            if asian_start <= candle.timestamp.astimezone(tz).time() < asian_end
        ]
        if len(asian_range) < 4:
            return None

        range_high = max(candle.high for candle in asian_range)
        range_low = min(candle.low for candle in asian_range)
        last_candle = candles[-1]

        atr_fast_period = int(strategy.entry.get("atr_fast", 4))
        atr_slow_period = int(strategy.entry.get("atr_slow", 16))
        contraction_ratio = float(strategy.entry.get("contraction_ratio", 0.8))
        atr_fast_value = atr(candles, atr_fast_period) or 0.0
        atr_slow_value = atr(candles, atr_slow_period) or 0.0
        range_contraction = atr_slow_value > 0 and atr_fast_value < atr_slow_value * contraction_ratio

        if last_candle.close > range_high and range_contraction:
            quality = min((last_candle.close - range_high) / max(range_high - range_low, 1e-6), 1.0)
            return self._candidate(
                SignalDirection.LONG,
                "london_breakout_long",
                quality,
                trend_alignment=0.75,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        if last_candle.close < range_low and range_contraction:
            quality = min((range_low - last_candle.close) / max(range_high - range_low, 1e-6), 1.0)
            return self._candidate(
                SignalDirection.SHORT,
                "london_breakout_short",
                quality,
                trend_alignment=0.75,
                market_state=market_state,
                instrument=strategy.instrument,
                candles=candles,
            )
        return None

    def _candidate(
        self,
        direction: SignalDirection,
        reason: str,
        signal_quality: float,
        trend_alignment: float,
        market_state: MarketState,
        instrument: str,
        candles: List[Candle],
    ) -> SignalCandidate:
        vol_score = self._volatility_score(market_state, instrument, candles)
        liquidity_score = self._liquidity_score(market_state, instrument)
        event_risk = market_state.features.get(instrument, {}).get("event_risk", 0.0)
        return SignalCandidate(
            direction=direction,
            reason=reason,
            signal_quality=_clamp(signal_quality),
            trend_alignment=_clamp(trend_alignment),
            volatility_regime=_clamp(vol_score),
            liquidity_score=_clamp(liquidity_score),
            event_risk=_clamp(event_risk),
        )

    def _compute_confidence(
        self,
        strategy: StrategyConfig,
        candidate: SignalCandidate,
        market_state: MarketState,
        model: Optional[ConfidenceModelConfig],
    ) -> float:
        inputs = model.inputs if model else []
        if not inputs:
            return 0.5
        values: Dict[str, float] = {
            "signal_quality": candidate.signal_quality,
            "trend_alignment": candidate.trend_alignment,
            "volatility_regime": candidate.volatility_regime,
            "liquidity_score": candidate.liquidity_score,
            "event_risk": candidate.event_risk,
        }

        weighted = 0.0
        total_weight = 0.0
        for entry in inputs:
            name = str(entry.get("name", ""))
            weight = float(entry.get("weight", 0.0))
            value = values.get(name, 0.5)
            weighted += weight * value
            total_weight += abs(weight)
        if total_weight == 0:
            return 0.5
        normalized = (weighted / total_weight + 1) / 2
        return _clamp(normalized)

    def _volatility_score(
        self, market_state: MarketState, instrument: str, candles: List[Candle]
    ) -> float:
        if instrument in market_state.volatility:
            vol = market_state.volatility[instrument]
            return _clamp(1.0 - abs(vol - 1.0) / 1.0)
        if len(candles) < 10:
            return 0.5
        avg_atr = atr(candles, 10)
        close = last_close(candles) or 0.0
        if avg_atr is None or close == 0:
            return 0.5
        vol_ratio = avg_atr / close
        target = 0.01
        return _clamp(1.0 - abs(vol_ratio - target) / target)

    @staticmethod
    def _liquidity_score(market_state: MarketState, instrument: str) -> float:
        if instrument in market_state.liquidity:
            return _clamp(market_state.liquidity[instrument])
        return 0.5

    @staticmethod
    def _get_candles(market_state: MarketState, strategy: StrategyConfig) -> List[Candle]:
        candles = market_state.candles.get(strategy.instrument, {}).get(strategy.timeframe, [])
        return sorted(candles, key=lambda c: c.timestamp)


def _session_window(timestamp: datetime, tz: ZoneInfo, hours: str) -> Tuple[datetime, datetime]:
    start_time, end_time = _parse_hours(hours)
    local_ts = timestamp.astimezone(tz)
    start = datetime.combine(local_ts.date(), start_time, tzinfo=tz)
    end = datetime.combine(local_ts.date(), end_time, tzinfo=tz)
    if end <= start:
        end = end + timedelta(days=1)
    return start, end


def _parse_hours(hours: str) -> Tuple[time, time]:
    start_str, end_str = hours.split("-")
    start_parts = [int(part) for part in start_str.split(":")]
    end_parts = [int(part) for part in end_str.split(":")]
    return time(start_parts[0], start_parts[1]), time(end_parts[0], end_parts[1])


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))
