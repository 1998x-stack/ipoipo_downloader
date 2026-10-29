"""Event schema: current state lives in SQLite; events are the audit history."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import json


@dataclass(frozen=True)
class Event:
    type: str
    post_id: str = ""
    stage: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
