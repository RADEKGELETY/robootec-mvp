import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core import strategy_registry
from core.strategy_registry import load_trading_config


@unittest.skipUnless(strategy_registry.YAML_AVAILABLE, "PyYAML not installed")
class TestStrategyRegistry(unittest.TestCase):
    def test_loads_yaml_config(self) -> None:
        config_path = ROOT / "config" / "trading_system.yaml"
        config = load_trading_config(config_path)
        self.assertEqual(config.system.currency, "USD")
        self.assertEqual(len(config.strategies), 5)
        self.assertIn("NASDAQ", config.portfolio.instruments)


if __name__ == "__main__":
    unittest.main()
