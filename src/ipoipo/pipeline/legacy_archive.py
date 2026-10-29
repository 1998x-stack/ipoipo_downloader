"""Audited, bounded offline import of archives left by v1/v2 collectors."""
from pathlib import Path
from typing import Any

from ipoipo.artifacts.local_import import import_local_archive, scan_old_archives
from ipoipo.persistence.repository import Repository
from ipoipo.settings import Settings


def migrate_archives(settings: Settings, repository: Repository, archive_dir: Path,
                     *, category: str | None = None, limit: int | None = None) -> dict[str, Any]:
    paths = scan_old_archives(archive_dir, category=category)
    if limit is not None:
        paths = paths[:limit]
    result: dict[str, Any] = {"scanned": len(paths), "imported": 0,
                              "failed": 0, "failures": []}
    for archive in paths:
        try:
            manifest, artifacts = import_local_archive(settings, archive)
        except (OSError, ValueError, RuntimeError) as exc:
            result["failed"] += 1
            result["failures"].append({"archive": str(archive), "reason": str(exc)})
            repository.audit_event("legacy_archive_rejected", stage="archive_import",
                                   archive=str(archive), error=str(exc))
        else:
            result["imported"] += 1
            repository.audit_event("legacy_archive_imported", stage="archive_import",
                                   archive_sha256=manifest.parent.name,
                                   artifact_count=len(artifacts))
    return result
