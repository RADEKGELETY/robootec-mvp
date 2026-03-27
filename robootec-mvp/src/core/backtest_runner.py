from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .audit_logger import AuditLogger
from .data_loader import load_ohlcv_csv
from .decision_engine import DecisionEngine, Exposure
from .execution_policy import ExecutionPolicy
from .market_regime import MarketRegime, evaluate_market_regime
from .market_state_engine import Candle, MarketState, MarketStateEngine
from .performance_evaluator import PerformanceEvaluator, PerformanceSummary, TradeResult
from .position_sizer import PositionSizer
from .risk_engine import RiskEngine
from .signal_engine import Signal, SignalDirection, SignalEngine
from .strategy_registry import StrategyConfig, TradingConfig
from .technical_indicators import atr


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path
    output_dir: Path
    max_holding_bars: int = 20
    atr_period: int = 14
    timezone: str = "UTC"


@dataclass
class Trade:
    id: str
    strategy_id: str
    instrument: str
    timeframe: str
    direction: SignalDirection
    entry_time: datetime
    entry_price: float
    stop_price: float
    target_price: float
    reason: str
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl_r: Optional[float] = None
    pnl_pct: Optional[float] = None
    bars_held: int = 0


@dataclass(frozen=True)
class BacktestSummary:
    trades: List[Trade]
    performance_by_strategy: Dict[str, PerformanceSummary]


@dataclass(frozen=True)
class CandleEvent:
    timestamp: datetime
    instrument: str
    timeframe: str
    candle: Candle


class BacktestRunner:
    def __init__(self, config: BacktestConfig, trading_config: TradingConfig) -> None:
        self._config = config
        self._trading_config = trading_config
        self._state_engine = MarketStateEngine()
        self._signal_engine = SignalEngine(trading_config.confidence_model)
        self._decision_engine = DecisionEngine(trading_config.decision_rules)
        self._risk_engine = RiskEngine(trading_config.global_risk)
        self._position_sizer = PositionSizer(
            trading_config.global_risk, trading_config.portfolio.capital_per_strategy
        )
        self._execution_policy = ExecutionPolicy()
        self._performance = PerformanceEvaluator()
        self._audit_logger = AuditLogger(config.output_dir / "audit.log")
        self._trade_log_path = config.output_dir / "trades.csv"

    def run(self) -> BacktestSummary:
        self._config.output_dir.mkdir(parents=True, exist_ok=True)
        strategies, series = self._load_series()
        events = self._build_timeline(series)
        if not events:
            return BacktestSummary(trades=[], performance_by_strategy={})

        strategy_by_id = {strategy.id: strategy for strategy in strategies}
        strategy_by_key: Dict[Tuple[str, str], List[StrategyConfig]] = {}
        for strategy in strategies:
            strategy_by_key.setdefault((strategy.instrument, strategy.timeframe), []).append(strategy)

        candles_by_key: Dict[str, Dict[str, List[Candle]]] = {}
        features: Dict[str, Dict[str, float]] = {}
        open_trades: Dict[str, Trade] = {}
        closed_trades: List[Trade] = []

        for event in events:
            candles_by_key.setdefault(event.instrument, {}).setdefault(event.timeframe, []).append(
                event.candle
            )

            regime = evaluate_market_regime(
                candles_by_key[event.instrument][event.timeframe]
            )
            features[event.instrument] = self._regime_to_features(regime)
            self._audit_logger.log(
                "market_regime",
                {
                    "instrument": event.instrument,
                    "timeframe": event.timeframe,
                    "timestamp": event.timestamp.isoformat(),
                    "regime": regime.label,
                    "trend_strength": regime.trend_strength,
                    "volatility": regime.volatility,
                },
            )

            market_state = self._state_engine.build_state(
                timestamp=event.timestamp,
                candles=candles_by_key,
                features=features,
            )

            self._update_open_trades(event, open_trades, closed_trades)

            strategies_for_event = strategy_by_key.get((event.instrument, event.timeframe), [])
            if not strategies_for_event:
                continue

            signals = self._signal_engine.generate_signals(
                strategies_for_event, market_state, self._trading_config.confidence_model
            )
            for signal in signals:
                if signal.strategy_id in open_trades:
                    continue
                strategy = strategy_by_id.get(signal.strategy_id)
                if strategy is None:
                    continue
                if self._risk_engine.is_in_cooldown(strategy.id, signal.timestamp):
                    continue

                exposures = [
                    Exposure(
                        strategy_id=trade.strategy_id,
                        instrument=trade.instrument,
                        direction=trade.direction.value,
                    )
                    for trade in open_trades.values()
                ]

                decision = self._decision_engine.evaluate(
                    strategy, signal, self._risk_engine, exposures
                )
                if not decision.allow:
                    self._audit_logger.log(
                        "signal_blocked",
                        {
                            "strategy_id": strategy.id,
                            "instrument": strategy.instrument,
                            "timestamp": signal.timestamp.isoformat(),
                            "reasons": decision.reasons,
                        },
                    )
                    continue

                trade = self._open_trade(strategy, signal, decision.size_multiplier, market_state)
                if trade is None:
                    continue
                open_trades[trade.strategy_id] = trade
                self._audit_logger.log(
                    "trade_open",
                    {
                        "strategy_id": trade.strategy_id,
                        "instrument": trade.instrument,
                        "direction": trade.direction.value,
                        "entry_time": trade.entry_time.isoformat(),
                        "entry_price": trade.entry_price,
                        "stop_price": trade.stop_price,
                        "target_price": trade.target_price,
                    },
                )

        last_event = events[-1]
        for trade in list(open_trades.values()):
            if trade.exit_time is None:
                trade.exit_time = last_event.timestamp
                trade.exit_price = last_event.candle.close
                self._finalize_trade(trade)
                closed_trades.append(trade)

        self._write_trade_log(closed_trades)
        performance_by_strategy = self._summarize_performance(closed_trades)
        self._write_summary(performance_by_strategy)

        return BacktestSummary(trades=closed_trades, performance_by_strategy=performance_by_strategy)

    def _load_series(self) -> Tuple[List[StrategyConfig], Dict[Tuple[str, str], List[Candle]]]:
        series: Dict[Tuple[str, str], List[Candle]] = {}
        strategies: List[StrategyConfig] = []
        for strategy in self._trading_config.strategies:
            data_path = self._find_data_file(strategy)
            if data_path is None:
                self._audit_logger.log(
                    "missing_data",
                    {"strategy_id": strategy.id, "instrument": strategy.instrument},
                )
                continue
            candles = load_ohlcv_csv(data_path, tz=self._config.timezone)
            series[(strategy.instrument, strategy.timeframe)] = candles
            strategies.append(strategy)

        return strategies, series

    def _find_data_file(self, strategy: StrategyConfig) -> Optional[Path]:
        direct = self._config.data_dir / f"{strategy.instrument}_{strategy.timeframe}.csv"
        if direct.exists():
            return direct
        nested = self._config.data_dir / strategy.instrument / f"{strategy.timeframe}.csv"
        if nested.exists():
            return nested
        fallback = self._config.data_dir / f"{strategy.instrument}.csv"
        if fallback.exists():
            return fallback
        return None

    @staticmethod
    def _build_timeline(
        series: Dict[Tuple[str, str], List[Candle]]
    ) -> List[CandleEvent]:
        events: List[CandleEvent] = []
        for (instrument, timeframe), candles in series.items():
            for candle in candles:
                events.append(
                    CandleEvent(
                        timestamp=candle.timestamp,
                        instrument=instrument,
                        timeframe=timeframe,
                        candle=candle,
                    )
                )
        events.sort(key=lambda event: event.timestamp)
        return events

    @staticmethod
    def _regime_to_features(regime: MarketRegime) -> Dict[str, float]:
        regime_code = {"trend": 1.0, "range": 0.0, "volatile": -1.0}.get(
            regime.label, 0.0
        )
        return {
            "trend_strength": regime.trend_strength,
            "volatility": regime.volatility,
            "regime_code": regime_code,
            "event_risk": 0.0,
        }

    def _open_trade(
        self,
        strategy: StrategyConfig,
        signal: Signal,
        size_multiplier: float,
        market_state: MarketState,
    ) -> Optional[Trade]:
        candles = market_state.candles.get(strategy.instrument, {}).get(strategy.timeframe, [])
        if len(candles) < self._config.atr_period:
            return None
        avg_atr = atr(candles, self._config.atr_period)
        if avg_atr is None or avg_atr <= 0:
            return None

        entry_price = candles[-1].close
        direction = signal.direction
        stop_price, target_price = self._build_levels(strategy, direction, entry_price, avg_atr)
        if stop_price == entry_price:
            return None

        risk_state = self._risk_engine.get_strategy_state(strategy.id)
        position = self._position_sizer.size_position(
            strategy, size_multiplier, risk_state.consecutive_losses
        )
        _ = self._execution_policy.build_plan(
            strategy, signal, self._trading_config.trade_management, position
        )

        return Trade(
            id=f"{strategy.id}-{signal.timestamp.isoformat()}",
            strategy_id=strategy.id,
            instrument=strategy.instrument,
            timeframe=strategy.timeframe,
            direction=direction,
            entry_time=signal.timestamp,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            reason=signal.reason,
        )

    @staticmethod
    def _build_levels(
        strategy: StrategyConfig,
        direction: SignalDirection,
        entry_price: float,
        atr_value: float,
    ) -> Tuple[float, float]:
        target_r = float(strategy.exit.get("target_r", 2.0))
        if direction == SignalDirection.LONG:
            stop = entry_price - atr_value
            target = entry_price + atr_value * target_r
        else:
            stop = entry_price + atr_value
            target = entry_price - atr_value * target_r
        return stop, target

    def _update_open_trades(
        self,
        event: CandleEvent,
        open_trades: Dict[str, Trade],
        closed_trades: List[Trade],
    ) -> None:
        to_close: List[str] = []
        for trade_id, trade in open_trades.items():
            if trade.instrument != event.instrument or trade.timeframe != event.timeframe:
                continue

            trade.bars_held += 1
            exit_price = self._check_exit(trade, event.candle)
            if exit_price is None:
                if trade.bars_held >= self._config.max_holding_bars:
                    exit_price = event.candle.close
            if exit_price is not None:
                trade.exit_time = event.timestamp
                trade.exit_price = exit_price
                self._finalize_trade(trade)
                closed_trades.append(trade)
                to_close.append(trade_id)
                self._audit_logger.log(
                    "trade_close",
                    {
                        "strategy_id": trade.strategy_id,
                        "instrument": trade.instrument,
                        "exit_time": trade.exit_time.isoformat(),
                        "exit_price": trade.exit_price,
                        "pnl_r": trade.pnl_r,
                        "pnl_pct": trade.pnl_pct,
                    },
                )

        for trade_id in to_close:
            open_trades.pop(trade_id, None)

    @staticmethod
    def _check_exit(trade: Trade, candle: Candle) -> Optional[float]:
        if trade.direction == SignalDirection.LONG:
            if candle.low <= trade.stop_price:
                return trade.stop_price
            if candle.high >= trade.target_price:
                return trade.target_price
        else:
            if candle.high >= trade.stop_price:
                return trade.stop_price
            if candle.low <= trade.target_price:
                return trade.target_price
        return None

    def _finalize_trade(self, trade: Trade) -> None:
        if trade.exit_price is None:
            return
        risk_per_unit = abs(trade.entry_price - trade.stop_price)
        if risk_per_unit == 0:
            trade.pnl_r = 0.0
        else:
            direction_sign = 1 if trade.direction == SignalDirection.LONG else -1
            trade.pnl_r = (trade.exit_price - trade.entry_price) * direction_sign / risk_per_unit
        trade.pnl_pct = (
            (trade.exit_price - trade.entry_price)
            / trade.entry_price
            * (1 if trade.direction == SignalDirection.LONG else -1)
            * 100.0
        )
        self._risk_engine.record_trade_result(
            trade.strategy_id, trade.pnl_pct, trade.exit_time or trade.entry_time
        )
        if trade.pnl_pct < 0:
            self._risk_engine.record_portfolio_day_loss(trade.pnl_pct)

    def _write_trade_log(self, trades: List[Trade]) -> None:
        with self._trade_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "trade_id",
                    "strategy_id",
                    "instrument",
                    "timeframe",
                    "direction",
                    "entry_time",
                    "entry_price",
                    "stop_price",
                    "target_price",
                    "exit_time",
                    "exit_price",
                    "pnl_r",
                    "pnl_pct",
                    "bars_held",
                    "reason",
                ]
            )
            for trade in trades:
                writer.writerow(
                    [
                        trade.id,
                        trade.strategy_id,
                        trade.instrument,
                        trade.timeframe,
                        trade.direction.value,
                        trade.entry_time.isoformat(),
                        trade.entry_price,
                        trade.stop_price,
                        trade.target_price,
                        trade.exit_time.isoformat() if trade.exit_time else "",
                        trade.exit_price if trade.exit_price is not None else "",
                        trade.pnl_r if trade.pnl_r is not None else "",
                        trade.pnl_pct if trade.pnl_pct is not None else "",
                        trade.bars_held,
                        trade.reason,
                    ]
                )

    def _summarize_performance(
        self, trades: List[Trade]
    ) -> Dict[str, PerformanceSummary]:
        by_strategy: Dict[str, List[TradeResult]] = {}
        for trade in trades:
            if trade.pnl_r is None or trade.pnl_pct is None:
                continue
            by_strategy.setdefault(trade.strategy_id, []).append(
                TradeResult(pnl_r=trade.pnl_r, pnl_pct=trade.pnl_pct)
            )

        summary: Dict[str, PerformanceSummary] = {}
        for strategy_id, results in by_strategy.items():
            summary[strategy_id] = self._performance.evaluate(results)
        return summary

    def _write_summary(self, summary: Dict[str, PerformanceSummary]) -> None:
        path = self._config.output_dir / "summary.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["strategy_id", "trades", "win_rate", "avg_r", "profit_factor"])
            for strategy_id, stats in summary.items():
                writer.writerow(
                    [
                        strategy_id,
                        stats.trades,
                        round(stats.win_rate, 4),
                        round(stats.avg_r, 4),
                        round(stats.profit_factor, 4),
                    ]
                )
