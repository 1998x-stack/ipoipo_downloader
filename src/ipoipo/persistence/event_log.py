"""Export canonical SQLite audit events to machine-readable JSONL."""
import json
import os
from pathlib import Path

from ipoipo.persistence.repository import Repository


def export_events(repository: Repository, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    events = repository.events()
    with temporary.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return len(events)
