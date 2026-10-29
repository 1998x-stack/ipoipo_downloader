"""SQLite schema, WAL and explicit transaction boundaries."""
import sqlite3
from importlib.resources import files
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = files("ipoipo.persistence.migrations").joinpath("0001_initial.sql").read_text(encoding="utf-8")


class Database:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=30, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA foreign_keys=ON")
            current_version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
            if current_version > 1:
                raise RuntimeError(f"Unsupported newer SQLite schema version: {current_version}")
            self.conn.executescript(SCHEMA)
            if current_version == 0:
                self.conn.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.commit()
            except BaseException:
                self.conn.rollback()
                raise

    def close(self) -> None:
        with self.lock:
            self.conn.close()
