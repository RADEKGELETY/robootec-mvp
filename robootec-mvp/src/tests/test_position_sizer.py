import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core.strategy_registry import load_trading_config, YAML_AVAILABLE
from core.position_sizer import PositionSizer


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestPositionSizer(unittest.TestCase):
    def test_loss_streak_reduces_size(self) -> None:
        config_path = ROOT / "config" / "trading_system.yaml"
        config = load_trading_config(config_path)
        strategy = config.strategies[0]
        sizer = PositionSizer(config.global_risk, config.portfolio.capital_per_strategy)

        size = sizer.size_position(strategy, confidence_multiplier=1.0, consecutive_losses=2)
        self.assertAlmostEqual(size.size_multiplier, 0.5, places=4)
        self.assertAlmostEqual(size.risk_pct, 0.25, places=4)


if __name__ == "__main__":
    unittest.main()
