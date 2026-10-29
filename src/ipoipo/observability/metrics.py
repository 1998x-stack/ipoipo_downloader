"""Compute run-level delivery rates using canonical repository state."""
from ipoipo.persistence.repository import Repository


def snapshot(repository: Repository) -> dict:
    stats = repository.stats()
    grouped = stats["tasks"]
    done = grouped.get("download:succeeded", 0)
    failed = grouped.get("download:failed", 0)
    total = done + failed
    return {**stats, "download_terminal_success_rate": done / total if total else None}
