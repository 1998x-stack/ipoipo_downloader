"""Recover interrupted leases and reconcile committed manifests against SQLite."""
import time
from pathlib import Path
from ipoipo.artifacts.validator import verified_manifest
from ipoipo.persistence.repository import Repository


def recover(repository: Repository, download_dir: Path) -> dict[str, int]:
    leases = repository.recover_expired()
    repaired = 0
    with repository.db.transaction() as c:
        completed = c.execute("""SELECT post_id FROM tasks WHERE stage='download'
                                  AND status='succeeded'""").fetchall()
        for row in completed:
            post_id = row["post_id"]
            if verified_manifest(download_dir / post_id) is not None:
                continue
            c.execute("""UPDATE tasks SET status='pending', attempts=0, available_at=0,
                         owner=NULL,lease_until=NULL,last_error='missing or corrupt artifact',
                         updated_at=? WHERE post_id=? AND stage='download'""",
                      (time.time(), post_id))
            c.execute("DELETE FROM artifacts WHERE post_id=?", (post_id,))
            repository._event(c, "artifact_reconciliation_failed", post_id, "download")
            repaired += 1
    return {"expired_leases": leases, "requeued_invalid_artifacts": repaired}
