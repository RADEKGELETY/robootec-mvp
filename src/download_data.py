from __future__ import annotations

import argparse
import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import requests


def _month_sequence(end: datetime, months: int) -> List[Tuple[int, int]]:
    if months <= 0:
        return []
    y = end.year
    m = end.month
    result: List[Tuple[int, int]] = []
    for _ in range(months):
        result.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(result))


def _interval_to_timeframe(interval: str) -> str:
    interval = interval.strip().lower()
    if interval.endswith("min"):
        return f"{interval.replace('min', '')}m"
    return interval


def _parse_alpha_timestamp(value: str, tz: ZoneInfo) -> datetime:
    ts = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return ts.replace(tzinfo=tz)


def _rows_from_csv(text: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(text.splitlines())
    return list(reader)


@dataclass
class DownloadConfig:
    symbol: str
    instrument: str
    interval: str
    months: int
    api_key: str
    output_path: Path
    tz: str


class AlphaVantageDownloader:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, config: DownloadConfig) -> None:
        self._config = config
        self._tz = ZoneInfo(config.tz)

    def download(self) -> Path:
        now = datetime.now(tz=self._tz)
        months = _month_sequence(now, self._config.months)
        rows_by_time: Dict[str, Dict[str, str]] = {}

        for idx, (year, month) in enumerate(months):
            response_text = self._fetch_month(year, month)
            rows = _rows_from_csv(response_text)
            for row in rows:
                timestamp = row.get("timestamp")
                if not timestamp:
                    continue
                rows_by_time[timestamp] = row
            if idx < len(months) - 1:
                time.sleep(12)

        sorted_rows = [rows_by_time[key] for key in sorted(rows_by_time.keys())]
        self._write_output(sorted_rows)
        return self._config.output_path

    def _fetch_month(self, year: int, month: int) -> str:
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": self._config.symbol,
            "interval": self._config.interval,
            "month": f"{year}-{month:02d}",
            "outputsize": "full",
            "datatype": "csv",
            "apikey": self._config.api_key,
        }
        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.text

    def _write_output(self, rows: List[Dict[str, str]]) -> None:
        self._config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config.output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for row in rows:
                raw_ts = row.get("timestamp")
                if raw_ts is None:
                    continue
                ts_local = _parse_alpha_timestamp(raw_ts, self._tz)
                ts_utc = ts_local.astimezone(ZoneInfo("UTC"))
                writer.writerow(
                    [
                        ts_utc.replace(tzinfo=ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
                        row.get("open", "0"),
                        row.get("high", "0"),
                        row.get("low", "0"),
                        row.get("close", "0"),
                        row.get("volume", "0"),
                    ]
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NASDAQ intraday data via Alpha Vantage")
    parser.add_argument("--symbol", type=str, default="QQQ", help="Ticker symbol (e.g., QQQ)")
    parser.add_argument(
        "--instrument",
        type=str,
        default="NASDAQ",
        help="Instrument name used in filename (e.g., NASDAQ)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="5min",
        choices=["5min", "15min"],
        help="Intraday interval",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="How many months of data to download",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("ALPHAVANTAGE_API_KEY", ""),
        help="Alpha Vantage API key (or set ALPHAVANTAGE_API_KEY env var)",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="America/New_York",
        help="Timezone of the Alpha Vantage timestamp",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
        help="Output directory for CSV",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Missing API key. Provide --api-key or set ALPHAVANTAGE_API_KEY.")

    timeframe = _interval_to_timeframe(args.interval)
    output_path = args.output_dir / f"{args.instrument}_{timeframe}.csv"

    config = DownloadConfig(
        symbol=args.symbol,
        instrument=args.instrument,
        interval=args.interval,
        months=args.months,
        api_key=args.api_key,
        output_path=output_path,
        tz=args.timezone,
    )

    downloader = AlphaVantageDownloader(config)
    path = downloader.download()
    print(f"Saved data to {path}")


if __name__ == "__main__":
    main()
