from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - handled by runtime check
    yaml = None

YAML_AVAILABLE = yaml is not None


@dataclass(frozen=True)
class SystemConfig:
    name: str
    currency: str


@dataclass(frozen=True)
class PortfolioConfig:
    capital_per_strategy: float
    instruments: List[str]


@dataclass(frozen=True)
class GlobalRiskConfig:
    max_daily_loss_per_strategy_pct: float
    max_weekly_drawdown_per_strategy_pct: float
    max_portfolio_daily_loss_pct: float
    max_consecutive_losses_before_cooldown: int
    loss_streak_after_losses: int
    loss_streak_reduction_pct: float
    cooldown_after_losses: int
    cooldown_duration_minutes: int


@dataclass(frozen=True)
class TradeManagementConfig:
    break_even_at_r: float
    partial_exit_at_r: float
    partial_exit_close_pct: float
    trailing_stop_enabled_for_types: List[str]
    trailing_stop_atr_period: int
    trailing_stop_atr_multiple: float


@dataclass(frozen=True)
class ExecutionConfig:
    slippage_bps: float
    fee_bps: float


@dataclass(frozen=True)
class ConfidenceModelConfig:
    name: str
    min_to_trade: float
    min_for_full_size: float
    inputs: List[Dict[str, Any]]
    calibration: Dict[str, Any]


@dataclass(frozen=True)
class DecisionRule:
    id: str
    action: str
    conditions: List[Dict[str, Any]]
    buckets: List[Dict[str, Any]]


@dataclass(frozen=True)
class StrategyConfig:
    id: str
    instrument: str
    type: str
    timeframe: str
    session_timezone: str
    session_hours: str
    entry: Dict[str, Any]
    exit: Dict[str, Any]
    risk: Dict[str, Any]


@dataclass(frozen=True)
class TradingConfig:
    system: SystemConfig
    portfolio: PortfolioConfig
    global_risk: GlobalRiskConfig
    trade_management: TradeManagementConfig
    execution: ExecutionConfig
    confidence_model: ConfidenceModelConfig
    decision_rules: List[DecisionRule]
    strategies: List[StrategyConfig]
    raw: Dict[str, Any]


def _require_yaml() -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML configs. Please install pyyaml.")


def _read_yaml(path: Path) -> Dict[str, Any]:
    _require_yaml()
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)  # type: ignore[union-attr]
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping.")
    return data


def _get_required(mapping: Dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise KeyError(f"Missing required key: {key}")
    return mapping[key]


def load_trading_config(path: str | Path) -> TradingConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)

    system = SystemConfig(
        name=str(_get_required(data, "system")["name"]),
        currency=str(_get_required(data, "system")["currency"]),
    )

    portfolio_data = _get_required(data, "portfolio")
    portfolio = PortfolioConfig(
        capital_per_strategy=float(portfolio_data["capital_allocation"]["per_strategy"]),
        instruments=list(portfolio_data["instruments"]),
    )

    global_risk_data = _get_required(data, "global_risk")
    global_risk = GlobalRiskConfig(
        max_daily_loss_per_strategy_pct=float(global_risk_data["max_daily_loss_per_strategy_pct"]),
        max_weekly_drawdown_per_strategy_pct=float(global_risk_data["max_weekly_drawdown_per_strategy_pct"]),
        max_portfolio_daily_loss_pct=float(global_risk_data["max_portfolio_daily_loss_pct"]),
        max_consecutive_losses_before_cooldown=int(global_risk_data["max_consecutive_losses_before_cooldown"]),
        loss_streak_after_losses=int(global_risk_data["loss_streak_size_reduction"]["after_losses"]),
        loss_streak_reduction_pct=float(global_risk_data["loss_streak_size_reduction"]["reduction_pct"]),
        cooldown_after_losses=int(global_risk_data["cooldown"]["after_losses"]),
        cooldown_duration_minutes=int(global_risk_data["cooldown"]["duration_minutes"]),
    )

    trade_mgmt_data = _get_required(data, "trade_management")
    trade_management = TradeManagementConfig(
        break_even_at_r=float(trade_mgmt_data["break_even_at_r"]),
        partial_exit_at_r=float(trade_mgmt_data["partial_exit"]["at_r"]),
        partial_exit_close_pct=float(trade_mgmt_data["partial_exit"]["close_pct"]),
        trailing_stop_enabled_for_types=list(trade_mgmt_data["trailing_stop"]["enabled_for_strategy_types"]),
        trailing_stop_atr_period=int(trade_mgmt_data["trailing_stop"].get("atr_period", 14)),
        trailing_stop_atr_multiple=float(trade_mgmt_data["trailing_stop"].get("atr_multiple", 2.0)),
    )

    execution_data = data.get("execution", {})
    execution = ExecutionConfig(
        slippage_bps=float(execution_data.get("slippage_bps", 0.0)),
        fee_bps=float(execution_data.get("fee_bps", 0.0)),
    )

    confidence_data = _get_required(data, "confidence_model")
    confidence_model = ConfidenceModelConfig(
        name=str(confidence_data["name"]),
        min_to_trade=float(confidence_data["thresholds"]["min_to_trade"]),
        min_for_full_size=float(confidence_data["thresholds"]["min_for_full_size"]),
        inputs=list(confidence_data.get("inputs", [])),
        calibration=dict(confidence_data.get("calibration", {})),
    )

    decision_rules: List[DecisionRule] = []
    decision_data = _get_required(data, "decision_engine")
    for rule in decision_data.get("rules", []):
        decision_rules.append(
            DecisionRule(
                id=str(rule.get("id", "")),
                action=str(rule.get("action", "")),
                conditions=list(rule.get("conditions", [])),
                buckets=list(rule.get("buckets", [])),
            )
        )

    strategies: List[StrategyConfig] = []
    for strategy in data.get("strategies", []):
        session = strategy.get("session", {})
        strategies.append(
            StrategyConfig(
                id=str(strategy["id"]),
                instrument=str(strategy["instrument"]),
                type=str(strategy["type"]),
                timeframe=str(strategy["timeframe"]),
                session_timezone=str(session.get("timezone", "UTC")),
                session_hours=str(session.get("hours", "00:00-23:59")),
                entry=dict(strategy.get("entry", {})),
                exit=dict(strategy.get("exit", {})),
                risk=dict(strategy.get("risk", {})),
            )
        )

    return TradingConfig(
        system=system,
        portfolio=portfolio,
        global_risk=global_risk,
        trade_management=trade_management,
        execution=execution,
        confidence_model=confidence_model,
        decision_rules=decision_rules,
        strategies=strategies,
        raw=data,
    )
