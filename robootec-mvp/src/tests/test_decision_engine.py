import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core.decision_engine import DecisionEngine
from core.risk_engine import RiskEngine
from core.signal_engine import Signal, SignalDirection
from core.strategy_registry import load_trading_config, YAML_AVAILABLE


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestDecisionEngine(unittest.TestCase):
    def test_blocks_on_low_confidence(self) -> None:
        config_path = ROOT / "config" / "trading_system.yaml"
        config = load_trading_config(config_path)
        strategy = config.strategies[0]

        engine = DecisionEngine(config.decision_rules)
        risk_engine = RiskEngine(config.global_risk)

        signal = Signal(
            strategy_id=strategy.id,
            instrument=strategy.instrument,
            direction=SignalDirection.LONG,
            confidence=0.50,
            timestamp=datetime(2026, 3, 27, 14, 0, tzinfo=timezone.utc),
            reason="test",
        )

        result = engine.evaluate(strategy, signal, risk_engine, exposures=[])
        self.assertFalse(result.allow)
        self.assertIn("confidence_below_threshold", result.reasons)


if __name__ == "__main__":
    unittest.main()
