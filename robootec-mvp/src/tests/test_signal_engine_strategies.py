import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core.market_state_engine import Candle, MarketStateEngine
from core.signal_engine import SignalDirection, SignalEngine
from core.strategy_registry import load_trading_config, YAML_AVAILABLE


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestSignalEngineStrategies(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = ROOT / "config" / "trading_system.yaml"
        self.config = load_trading_config(self.config_path)
        self.engine = SignalEngine(self.config.confidence_model)
        self.state_engine = MarketStateEngine()

    def test_orb_momentum(self) -> None:
        strategy = next(s for s in self.config.strategies if s.id == "NAS_01_ORB_MOMENTUM")
        tz = ZoneInfo("America/New_York")
        base = datetime(2026, 3, 27, 9, 30, tzinfo=tz)
        candles = [
            Candle(base, 100.0, 101.0, 99.5, 100.5, 100),
            Candle(base + timedelta(minutes=5), 100.5, 101.2, 100.0, 101.0, 110),
            Candle(base + timedelta(minutes=10), 101.0, 101.0, 99.8, 100.2, 90),
            Candle(base + timedelta(minutes=15), 101.0, 102.5, 100.8, 102.2, 250),
        ]
        market_state = self.state_engine.build_state(
            timestamp=candles[-1].timestamp,
            candles={"NASDAQ": {"5m": candles}},
        )
        signals = self.engine.generate_signals([strategy], market_state, self.config.confidence_model)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.LONG)

    def test_vwap_pullback(self) -> None:
        strategy = next(s for s in self.config.strategies if s.id == "NAS_02_VWAP_PULLBACK")
        tz = ZoneInfo("America/New_York")
        base = datetime(2026, 3, 27, 10, 0, tzinfo=tz)
        candles = []
        for i in range(25):
            price = 100.0
            candles.append(Candle(base + timedelta(minutes=5 * i), price, price + 0.1, price - 0.1, price, 100))
        for i in range(25, 30):
            price = 100.2
            candles.append(Candle(base + timedelta(minutes=5 * i), price, price + 0.05, price - 0.05, price, 100))
        market_state = self.state_engine.build_state(
            timestamp=candles[-1].timestamp,
            candles={"NASDAQ": {"5m": candles}},
        )
        signals = self.engine.generate_signals([strategy], market_state, self.config.confidence_model)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.LONG)

    def test_macro_trend_pullback(self) -> None:
        strategy = next(s for s in self.config.strategies if s.id == "XAU_02_MACRO_TREND_PULLBACK")
        tz = ZoneInfo("UTC")
        base = datetime(2026, 3, 25, 0, 0, tzinfo=tz)
        candles = []
        price = 2000.0
        for i in range(60):
            price += 0.2
            candles.append(
                Candle(
                    base + timedelta(hours=i),
                    price - 0.1,
                    price + 0.3,
                    price - 0.2,
                    price,
                    500,
                )
            )
        market_state = self.state_engine.build_state(
            timestamp=candles[-1].timestamp,
            candles={"GOLD": {"1h": candles}},
        )
        signals = self.engine.generate_signals([strategy], market_state, self.config.confidence_model)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.LONG)

    def test_daily_breakout_retest(self) -> None:
        strategy = next(s for s in self.config.strategies if s.id == "BTC_01_DAILY_BREAKOUT_RETEST")
        tz = ZoneInfo("UTC")
        base = datetime(2026, 3, 1, 0, 0, tzinfo=tz)
        candles = []
        for i in range(20):
            high = 100.0
            candles.append(
                Candle(
                    base + timedelta(days=i),
                    98.0,
                    high,
                    97.5,
                    99.5,
                    1000,
                )
            )
        candles.append(
            Candle(base + timedelta(days=20), 100.0, 106.0, 99.0, 105.0, 1200)
        )
        candles.append(
            Candle(base + timedelta(days=21), 105.0, 106.5, 100.2, 106.0, 1400)
        )
        market_state = self.state_engine.build_state(
            timestamp=candles[-1].timestamp,
            candles={"BITCOIN": {"1d": candles}},
        )
        signals = self.engine.generate_signals([strategy], market_state, self.config.confidence_model)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.LONG)

    def test_london_breakout(self) -> None:
        strategy = next(s for s in self.config.strategies if s.id == "FX_01_LONDON_BREAKOUT")
        tz = ZoneInfo("Europe/London")
        base = datetime(2026, 3, 27, 0, 0, tzinfo=tz)
        candles = []
        for i in range(16):
            ts = base + timedelta(minutes=15 * i)
            candles.append(Candle(ts, 1.1000, 1.1010, 1.0990, 1.1005, 1000))
        for i in range(16, 28):
            ts = base + timedelta(minutes=15 * i)
            candles.append(Candle(ts, 1.1005, 1.1007, 1.1003, 1.1006, 800))
        breakout_ts = base + timedelta(hours=7, minutes=15)
        candles.append(Candle(breakout_ts, 1.1010, 1.1016, 1.1010, 1.1015, 1200))
        market_state = self.state_engine.build_state(
            timestamp=candles[-1].timestamp,
            candles={"EURUSD": {"15m": candles}},
        )
        signals = self.engine.generate_signals([strategy], market_state, self.config.confidence_model)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.LONG)


if __name__ == "__main__":
    unittest.main()
