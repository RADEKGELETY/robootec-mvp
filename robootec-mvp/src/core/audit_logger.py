from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    event_type: str
    payload: Dict[str, Any]


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            payload=payload,
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event)) + "\n")
