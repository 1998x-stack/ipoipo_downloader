"""Real child-process exit, followed by lease expiry and fenced recovery."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from ipoipo.persistence.repository import Repository


def test_process_crash_lease_can_be_recovered(tmp_path):
    db = tmp_path / "crawl.sqlite3"
    setup = Repository(db)
    try:
        setup.upsert_category("85", "AI", "https://ipoipo.cn/tags-85.html")
    finally:
        setup.close()
    program = """
import os
from pathlib import Path
from ipoipo.persistence.repository import Repository
repo = Repository(Path(os.environ["DB_PATH"]))
assert repo.acquire_category_lease("85", "crashed-process", 60)
repo.save_checkpoint("85", 7, owner="crashed-process")
os._exit(15)
"""
    env = dict(os.environ, DB_PATH=str(db))
    child = subprocess.run([sys.executable, "-c", program], env=env, timeout=10)
    assert child.returncode == 15
    repo = Repository(db)
    try:
        assert not repo.acquire_category_lease("85", "next-process", 10)
        assert repo.checkpoint("85") == (7, False)
        with repo.db.transaction() as c:
            c.execute("UPDATE category_leases SET lease_until=? WHERE category_id='85'",
                      (time.time() - 2,))
        assert repo.acquire_category_lease("85", "next-process", 60)
        with pytest.raises(RuntimeError, match="Category lease"):
            repo.save_checkpoint("85", 1, owner="crashed-process")
        repo.save_checkpoint("85", 8, owner="next-process")
        assert repo.checkpoint("85") == (8, False)
    finally:
        repo.close()
