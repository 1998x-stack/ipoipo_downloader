import sqlite3
import time

import pytest

from ipoipo.persistence.repository import Repository
from ipoipo.persistence.sqlite import Database, SCHEMA


def test_two_processes_claim_exclusively_and_fence_checkpoint(tmp_path):
    path = tmp_path / "task.sqlite3"
    first, other = Repository(path), Repository(path)
    try:
        first.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        assert first.acquire_category_lease("85", "process-A", 60)
        assert not other.acquire_category_lease("85", "process-B", 60)
        first.save_checkpoint("85", 9, owner="process-A")
        with pytest.raises(RuntimeError, match="lease"):
            other.save_checkpoint("85", 2, owner="process-B")
        assert other.checkpoint("85") == (9, False)
        with pytest.raises(RuntimeError, match="leased"):
            other.reset_checkpoints("85")
        assert not other.release_category_lease("85", "process-B")
        assert first.release_category_lease("85", "process-A")
        assert other.acquire_category_lease("85", "process-B", 60)
        other.save_checkpoint("85", 10, owner="process-B")
        assert other.checkpoint("85") == (10, False)
    finally:
        first.close()
        other.close()


def test_crashed_owner_can_be_replaced_after_expiry(tmp_path):
    a, b = Repository(tmp_path / "db.sqlite3"), Repository(tmp_path / "db.sqlite3")
    try:
        a.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
        assert a.acquire_category_lease("85", "crashed", 1)
        with a.db.transaction() as c:
            c.execute("UPDATE category_leases SET lease_until=? WHERE category_id='85'",
                      (time.time() - 1,))
        assert b.acquire_category_lease("85", "replacement", 120)
        assert not a.release_category_lease("85", "crashed")
        with pytest.raises(RuntimeError):
            a.renew_category_lease("85", "crashed", 60)
        with pytest.raises(RuntimeError):
            a.save_checkpoint("85", 11, owner="crashed")
        assert b.renew_category_lease("85", "replacement", 60) is None
        b.save_checkpoint("85", 12, owner="replacement")
    finally:
        a.close()
        b.close()


def test_migrate_existing_v1_db_without_destroying_rows(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA user_version=1")
    conn.execute("INSERT INTO categories VALUES('85','AI','https://ipoipo.cn/tags-85.html')")
    conn.commit()
    conn.close()
    upgraded = Database(path)
    try:
        assert upgraded.conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert upgraded.conn.execute("SELECT name FROM categories WHERE category_id='85'").fetchone()[0] == "AI"
        assert upgraded.conn.execute("SELECT name FROM sqlite_master WHERE name='category_leases'").fetchone()
    finally:
        upgraded.close()


def test_migration_opened_twice_is_idempotent(tmp_path):
    path = tmp_path / "db.sqlite3"
    a, b = Repository(path), Repository(path)
    try:
        assert a.db.conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert b.db.conn.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        a.close()
        b.close()
