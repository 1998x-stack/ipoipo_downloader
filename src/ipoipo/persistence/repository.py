"""Transactional task store. All state changes and audit events share one transaction."""
import json
import time
from pathlib import Path
from typing import Any

from ipoipo.domain.models import Artifact, Report, Task
from ipoipo.domain.states import Stage, Status
from ipoipo.persistence.sqlite import Database


class Repository:
    def __init__(self, path: Path):
        self.db = Database(path)

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _event(c, kind: str, post_id: str = "", stage: str = "", **details: Any) -> None:
        c.execute("INSERT INTO events(ts,type,post_id,stage,details) VALUES(?,?,?,?,?)",
                  (time.time(), kind, post_id, stage, json.dumps(details, ensure_ascii=False)))

    def upsert_category(self, category_id: str, name: str, url: str) -> None:
        with self.db.transaction() as c:
            c.execute("INSERT INTO categories VALUES(?,?,?) ON CONFLICT(category_id) DO UPDATE SET name=excluded.name, source_url=excluded.source_url",
                      (category_id, name, url))
            c.execute("INSERT OR IGNORE INTO crawl_checkpoints(category_id,next_page,complete,updated_at) VALUES(?,1,0,?)",
                      (category_id, time.time()))

    def categories(self, category_id: str | None = None) -> list[dict[str, Any]]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT category_id,name,source_url FROM categories WHERE (? IS NULL OR category_id=?) ORDER BY category_id",
                (category_id, category_id)).fetchall()
        return [dict(row) for row in rows]

    def upsert_report(self, report: Report) -> bool:
        """Return True if first discovery. Rediscovery never resets succeeded tasks."""
        now = time.time()
        with self.db.transaction() as c:
            old = c.execute("SELECT post_id FROM reports WHERE post_id=?", (report.post_id,)).fetchone()
            c.execute("""INSERT INTO reports(post_id,title,detail_url,publish_date,thumbnail_url,description,view_count,discovered_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(post_id) DO UPDATE SET
                  title=excluded.title, detail_url=excluded.detail_url,
                  publish_date=excluded.publish_date, thumbnail_url=excluded.thumbnail_url,
                  description=excluded.description, view_count=excluded.view_count, updated_at=excluded.updated_at""",
                (report.post_id, report.title, report.detail_url, report.publish_date, report.thumbnail_url,
                 report.description, report.view_count, now, now))
            c.execute("INSERT OR IGNORE INTO report_categories(post_id,category_id) VALUES(?,?)",
                      (report.post_id, report.category_id))
            c.execute("INSERT OR IGNORE INTO tasks(post_id,stage,updated_at) VALUES(?,?,?)",
                      (report.post_id, Stage.RESOLVE, now))
            if old is None:
                self._event(c, "report_discovered", report.post_id, details_title=report.title)
            return old is None

    def checkpoint(self, category_id: str) -> tuple[int, bool]:
        with self.db.lock:
            row = self.db.conn.execute("SELECT next_page,complete FROM crawl_checkpoints WHERE category_id=?",
                                       (category_id,)).fetchone()
        return (int(row["next_page"]), bool(row["complete"])) if row else (1, False)

    def save_checkpoint(self, category_id: str, next_page: int, complete: bool = False) -> None:
        if next_page < 1:
            raise ValueError("next_page must be >= 1")
        with self.db.transaction() as c:
            c.execute("""INSERT INTO crawl_checkpoints(category_id,next_page,complete,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(category_id) DO UPDATE SET
                next_page=excluded.next_page,complete=excluded.complete,updated_at=excluded.updated_at""",
                (category_id, next_page, int(complete), time.time()))

    def reset_checkpoints(self, category_id: str | None = None) -> None:
        with self.db.transaction() as c:
            if category_id:
                c.execute("UPDATE crawl_checkpoints SET next_page=1,complete=0 WHERE category_id=?", (category_id,))
            else:
                c.execute("UPDATE crawl_checkpoints SET next_page=1,complete=0")

    def report(self, post_id: str) -> dict[str, Any] | None:
        with self.db.lock:
            row = self.db.conn.execute("""SELECT r.*,c.category_id,c.name AS category_name
                FROM reports r JOIN report_categories rc ON rc.post_id=r.post_id
                JOIN categories c ON c.category_id=rc.category_id WHERE r.post_id=?
                ORDER BY c.category_id LIMIT 1""", (post_id,)).fetchone()
        return dict(row) if row else None

    def claim(self, stage: str, owner: str, *, limit: int = 1, lease_seconds: int = 300) -> list[Task]:
        if limit < 1 or lease_seconds < 1 or not owner:
            raise ValueError("Invalid claim arguments")
        now = time.time()
        with self.db.transaction() as c:
            rows = c.execute("""SELECT id,post_id,stage,attempts,max_attempts FROM tasks
                WHERE stage=? AND status IN ('pending','retry_wait') AND available_at<=?
                ORDER BY available_at,id LIMIT ?""", (stage, now, limit)).fetchall()
            result = []
            for r in rows:
                c.execute("""UPDATE tasks SET status='running', attempts=attempts+1,
                    owner=?,lease_until=?,updated_at=? WHERE id=?""",
                    (owner, now + lease_seconds, now, r["id"]))
                result.append(Task(r["id"], r["post_id"], r["stage"],
                                   r["attempts"] + 1, r["max_attempts"], owner))
                self._event(c, "task_claimed", r["post_id"], stage, attempt=r["attempts"] + 1, owner=owner)
            return result

    @staticmethod
    def _owned(c, task: Task) -> None:
        row = c.execute("SELECT status,owner FROM tasks WHERE id=?", (task.id,)).fetchone()
        if row is None or row["status"] != "running" or row["owner"] != task.owner:
            raise RuntimeError("Task lease not owned or no longer running")

    def resolved(self, task: Task, url: str) -> None:
        with self.db.transaction() as c:
            self._owned(c, task)
            c.execute("UPDATE reports SET download_url=?,updated_at=? WHERE post_id=?", (url, time.time(), task.post_id))
            c.execute("UPDATE tasks SET status='succeeded',owner=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                      (time.time(), task.id))
            c.execute("INSERT OR IGNORE INTO tasks(post_id,stage,updated_at) VALUES(?,?,?)",
                      (task.post_id, Stage.DOWNLOAD, time.time()))
            self._event(c, "url_resolved", task.post_id, task.stage, download_url=url)

    def downloaded(self, task: Task, artifacts: list[Artifact], manifest: Path) -> None:
        if not artifacts or not manifest.is_file():
            raise ValueError("Cannot complete download without validated artifacts and manifest")
        with self.db.transaction() as c:
            self._owned(c, task)
            for artifact in artifacts:
                if not artifact.path.is_file():
                    raise ValueError(f"Artifact missing: {artifact.path}")
                c.execute("""INSERT INTO artifacts(post_id,path,sha256,size,media_type)
                    VALUES(?,?,?,?,?) ON CONFLICT(post_id,path) DO UPDATE SET
                    sha256=excluded.sha256,size=excluded.size,media_type=excluded.media_type""",
                    (task.post_id, str(artifact.path), artifact.sha256, artifact.size, artifact.media_type))
            c.execute("UPDATE tasks SET status='succeeded',owner=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                      (time.time(), task.id))
            self._event(c, "download_completed", task.post_id, task.stage,
                        manifest=str(manifest), artifact_count=len(artifacts))

    def failed(self, task: Task, reason: str, *, retryable: bool = True) -> str:
        with self.db.transaction() as c:
            self._owned(c, task)
            status = Status.RETRY_WAIT if retryable and task.attempts < task.max_attempts else Status.FAILED
            delay = min(300, 2 ** task.attempts) if status == Status.RETRY_WAIT else 0
            c.execute("""UPDATE tasks SET status=?,available_at=?,owner=NULL,lease_until=NULL,
                last_error=?,updated_at=? WHERE id=?""",
                (status, time.time() + delay, reason[:1000], time.time(), task.id))
            self._event(c, "task_failed", task.post_id, task.stage,
                        reason=reason[:1000], retryable=status == Status.RETRY_WAIT)
            return str(status)

    def recover_expired(self) -> int:
        """Recover after worker crash; leases are checked on every runner startup."""
        now = time.time()
        with self.db.transaction() as c:
            rows = c.execute("SELECT id,post_id,stage,attempts,max_attempts FROM tasks WHERE status='running' AND lease_until<=?",
                             (now,)).fetchall()
            for r in rows:
                status = Status.RETRY_WAIT if r["attempts"] < r["max_attempts"] else Status.FAILED
                c.execute("""UPDATE tasks SET status=?,available_at=?,owner=NULL,lease_until=NULL,
                    last_error='expired lease',updated_at=? WHERE id=?""",
                    (status, now, now, r["id"]))
                self._event(c, "lease_recovered", r["post_id"], r["stage"], status=status)
            return len(rows)

    def retry_failed(self, stage: str | None = None) -> int:
        with self.db.transaction() as c:
            query = "SELECT id,post_id,stage FROM tasks WHERE status='failed'"
            params: tuple = ()
            if stage:
                query += " AND stage=?"
                params = (stage,)
            rows = c.execute(query, params).fetchall()
            for r in rows:
                c.execute("""UPDATE tasks SET status='pending',attempts=0,available_at=0,
                    owner=NULL,lease_until=NULL,last_error=NULL,updated_at=? WHERE id=?""",
                    (time.time(), r["id"]))
                self._event(c, "manual_retry", r["post_id"], r["stage"])
            return len(rows)

    def stats(self) -> dict[str, Any]:
        with self.db.lock:
            c = self.db.conn
            categories = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            reports = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            artifacts = c.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            tasks = c.execute("SELECT stage,status,COUNT(*) n FROM tasks GROUP BY stage,status").fetchall()
        return {"categories": categories, "reports": reports, "artifacts": artifacts,
                "tasks": {f"{r['stage']}:{r['status']}": r["n"] for r in tasks}}

    def events(self, after_id: int = 0) -> list[dict[str, Any]]:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT * FROM events WHERE id>? ORDER BY id", (after_id,)).fetchall()
        return [dict(r) for r in rows]
