import time
from ipoipo.domain.models import Artifact, Report
from ipoipo.persistence.repository import Repository


def make_report(post_id="101", category_id="85"):
    return Report(post_id, "测试报告", category_id, "AI", "https://ipoipo.cn/post/101.html")


def test_atomic_claim_and_rediscovery(tmp_path):
    path = tmp_path / "db.sqlite3"
    a, b = Repository(path), Repository(path)
    try:
        a.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        assert a.upsert_report(make_report())
        assert not a.upsert_report(make_report())
        claimed = a.claim("resolve", "worker-a")
        assert len(claimed) == 1
        assert b.claim("resolve", "worker-b") == []
        a.resolved(claimed[0], "https://ipo.ai-tag.cn/x.zip")
        assert a.claim("resolve", "worker-a") == []
        assert a.claim("download", "worker-a")[0].post_id == "101"
        assert not a.upsert_report(make_report())
        assert a.claim("resolve", "worker-b") == []
    finally:
        a.close()
        b.close()


def test_retry_terminal_and_manual_reset(tmp_path):
    repo = Repository(tmp_path / "state.db")
    try:
        repo.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        repo.upsert_report(make_report())
        task = repo.claim("resolve", "w")[0]
        assert repo.failed(task, "temporary") == "retry_wait"
        assert repo.claim("resolve", "w") == []
        with repo.db.transaction() as c:
            c.execute("UPDATE tasks SET available_at=0 WHERE id=?", (task.id,))
        task = repo.claim("resolve", "w")[0]
        assert repo.failed(task, "does not exist", retryable=False) == "failed"
        assert repo.retry_failed("resolve") == 1
        assert repo.claim("resolve", "w")
    finally:
        repo.close()


def test_expired_lease_recovery(tmp_path):
    repo = Repository(tmp_path / "state.db")
    try:
        repo.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        repo.upsert_report(make_report())
        task = repo.claim("resolve", "dead-worker")[0]
        with repo.db.transaction() as c:
            c.execute("UPDATE tasks SET lease_until=? WHERE id=?", (time.time()-1, task.id))
        assert repo.recover_expired() == 1
        assert repo.recover_expired() == 0
        assert repo.claim("resolve", "alive")[0].post_id == task.post_id
    finally:
        repo.close()


def test_checkpoint_not_reset_on_partial_run(tmp_path):
    repo = Repository(tmp_path / "state.db")
    try:
        repo.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        repo.save_checkpoint("85", 21)
        assert repo.checkpoint("85") == (21, False)
        repo.save_checkpoint("85", 1, complete=True)
        assert repo.checkpoint("85") == (1, True)
    finally:
        repo.close()
