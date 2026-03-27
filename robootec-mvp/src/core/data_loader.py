from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

from .market_state_engine import Candle


@dataclass(frozen=True)
class OHLCVSeries:
    instrument: str
    timeframe: str
    candles: List[Candle]


def load_ohlcv_csv(path: Path, tz: str = "UTC") -> List[Candle]:
    candles: List[Candle] = []
    tzinfo = ZoneInfo(tz)

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = _parse_timestamp(row, tzinfo)
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=float(row.get("open", 0.0)),
                    high=float(row.get("high", 0.0)),
                    low=float(row.get("low", 0.0)),
                    close=float(row.get("close", 0.0)),
                    volume=float(row.get("volume", 0.0)),
                )
            )

    candles.sort(key=lambda candle: candle.timestamp)
    return candles


def _parse_timestamp(row: Dict[str, str], tzinfo: ZoneInfo) -> datetime:
    raw = row.get("timestamp") or row.get("time") or row.get("date")
    if raw is None:
        raise ValueError("CSV must include a timestamp column (timestamp/time/date).")
    raw = raw.strip()
    if raw.isdigit():
        ts = datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return ts.astimezone(tzinfo)
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    ts = datetime.fromisoformat(raw)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=tzinfo)
    return ts.astimezone(tzinfo)
