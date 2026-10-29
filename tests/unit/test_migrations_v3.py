import sqlite3
import pytest
from ipoipo.persistence.sqlite import Database


def test_schema_version_and_reopen(tmp_path):
    db_file = tmp_path / "db.sqlite3"
    db = Database(db_file)
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    db.close()
    reopened = Database(db_file)
    try:
        assert reopened.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        reopened.close()


def test_future_schema_refused(tmp_path):
    path = tmp_path / "future.db"
    c = sqlite3.connect(path)
    c.execute("PRAGMA user_version=999")
    c.close()
    with pytest.raises(RuntimeError, match="Unsupported newer SQLite schema"):
        Database(path)
