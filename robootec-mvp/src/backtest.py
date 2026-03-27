from __future__ import annotations

import argparse
from pathlib import Path

from core import BacktestConfig, BacktestRunner, load_trading_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ROBOOTEC.AI MVP backtest")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "trading_system.yaml",
        help="Path to trading system YAML",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
        help="Directory with OHLCV CSV files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "output" / "backtest",
        help="Output directory for logs and summaries",
    )
    parser.add_argument("--timezone", type=str, default="UTC", help="Timezone for data")

    args = parser.parse_args()

    trading_config = load_trading_config(args.config)
    runner = BacktestRunner(
        BacktestConfig(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            timezone=args.timezone,
        ),
        trading_config,
    )
    runner.run()


if __name__ == "__main__":
    main()
