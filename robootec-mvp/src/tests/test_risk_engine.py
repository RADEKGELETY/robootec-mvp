import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core.risk_engine import RiskEngine, StrategyRiskState
from core.strategy_registry import load_trading_config, YAML_AVAILABLE


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestRiskEngine(unittest.TestCase):
    def test_daily_loss_breach(self) -> None:
        config_path = ROOT / "config" / "trading_system.yaml"
        config = load_trading_config(config_path)
        engine = RiskEngine(config.global_risk)

        state = StrategyRiskState(daily_loss_pct=2.5)
        engine.set_strategy_state("NAS_01_ORB_MOMENTUM", state)
        self.assertTrue(engine.is_risk_breached("NAS_01_ORB_MOMENTUM"))

    def test_cooldown_activation(self) -> None:
        config_path = ROOT / "config" / "trading_system.yaml"
        config = load_trading_config(config_path)
        engine = RiskEngine(config.global_risk)
        now = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)

        engine.record_trade_result("NAS_01_ORB_MOMENTUM", pnl_pct=-0.5, timestamp=now)
        engine.record_trade_result("NAS_01_ORB_MOMENTUM", pnl_pct=-0.5, timestamp=now)
        engine.record_trade_result("NAS_01_ORB_MOMENTUM", pnl_pct=-0.5, timestamp=now)

        self.assertTrue(engine.is_in_cooldown("NAS_01_ORB_MOMENTUM", now))


if __name__ == "__main__":
    unittest.main()
