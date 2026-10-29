"""Atomically written manifest with source lineage and content hashes."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ipoipo.domain.models import Artifact


def write_manifest(directory: Path, *, post_id: str, source_url: str, archive_sha256: str,
                   artifacts: list[Artifact]) -> Path:
    payload = {
        "schema_version": 1, "post_id": post_id, "source_url": source_url,
        "archive_sha256": archive_sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "documents": [{
            "path": str(a.path.relative_to(directory)),
            "sha256": a.sha256, "size": a.size, "media_type": a.media_type
        } for a in artifacts]}
    tmp = directory / "manifest.json.tmp"
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    output = directory / "manifest.json"
    os.replace(tmp, output)
    return output
