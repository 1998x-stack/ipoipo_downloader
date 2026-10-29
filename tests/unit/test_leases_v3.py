from ipoipo.domain.models import Report
from ipoipo.persistence.repository import Repository


def test_worker_can_renew_only_its_own_lease(tmp_path):
    repo = Repository(tmp_path / "db.sqlite3")
    try:
        repo.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        repo.upsert_report(Report("11", "A", "85", "AI", "https://ipoipo.cn/post/11.html"))
        task = repo.claim("resolve", "worker1", lease_seconds=1)[0]
        repo.renew_lease(task, 200)
        with repo.db.lock:
            ttl = repo.db.conn.execute("SELECT lease_until FROM tasks WHERE id=?", (task.id,)).fetchone()[0]
        import time
        assert ttl > time.time() + 100
        repo.resolved(task, "https://ipo.ai-tag.cn/11.zip")
    finally:
        repo.close()
