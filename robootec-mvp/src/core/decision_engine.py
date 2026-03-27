from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .market_state_engine import MarketStateEngine
from .risk_engine import RiskEngine
from .signal_engine import Signal
from .strategy_registry import DecisionRule, StrategyConfig


@dataclass(frozen=True)
class Exposure:
    strategy_id: str
    instrument: str
    direction: str


@dataclass(frozen=True)
class DecisionResult:
    allow: bool
    size_multiplier: float
    reasons: List[str]


class DecisionEngine:
    def __init__(self, rules: List[DecisionRule]) -> None:
        self._rules = rules
        self._market_state_engine = MarketStateEngine()

    def evaluate(
        self,
        strategy: StrategyConfig,
        signal: Signal,
        risk_engine: RiskEngine,
        exposures: List[Exposure],
    ) -> DecisionResult:
        allow = True
        size_multiplier = 1.0
        reasons: List[str] = []

        for rule in self._rules:
            if rule.id == "risk_gate":
                if risk_engine.is_risk_breached(strategy.id):
                    allow = False
                    reasons.append("risk_limit_breached")
            elif rule.id == "confidence_gate":
                threshold = rule.conditions[0].get("value", 0.0) if rule.conditions else 0.0
                if signal.confidence < float(threshold):
                    allow = False
                    reasons.append("confidence_below_threshold")
            elif rule.id == "size_scaling":
                size_multiplier = self._select_size_multiplier(rule, signal.confidence)
            elif rule.id == "session_filter":
                if not self._market_state_engine.is_strategy_in_session(
                    strategy, signal.timestamp
                ):
                    allow = False
                    reasons.append("outside_session")
            elif rule.id == "exposure_conflict":
                max_same_direction = 1
                for condition in rule.conditions:
                    if "max_same_direction_strategies" in condition:
                        max_same_direction = int(condition["max_same_direction_strategies"])
                same_direction = [
                    exposure
                    for exposure in exposures
                    if exposure.instrument == signal.instrument
                    and exposure.direction == signal.direction.value
                ]
                if len(same_direction) >= max_same_direction:
                    allow = False
                    reasons.append("conflicting_exposure")

        return DecisionResult(allow=allow, size_multiplier=size_multiplier, reasons=reasons)

    @staticmethod
    def _select_size_multiplier(rule: DecisionRule, confidence: float) -> float:
        for bucket in rule.buckets:
            min_conf = float(bucket.get("min_confidence", 0.0))
            max_conf = float(bucket.get("max_confidence", 1.0))
            if min_conf <= confidence <= max_conf:
                return float(bucket.get("size_multiplier", 1.0))
        return 1.0
