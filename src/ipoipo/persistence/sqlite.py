"""SQLite schema, WAL and explicit transaction boundaries."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
  category_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
  post_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  detail_url TEXT NOT NULL,
  publish_date TEXT NOT NULL DEFAULT '',
  thumbnail_url TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  view_count INTEGER NOT NULL DEFAULT 0,
  download_url TEXT,
  discovered_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS report_categories (
  post_id TEXT NOT NULL REFERENCES reports(post_id),
  category_id TEXT NOT NULL REFERENCES categories(category_id),
  PRIMARY KEY(post_id, category_id)
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id TEXT NOT NULL REFERENCES reports(post_id),
  stage TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  available_at REAL NOT NULL DEFAULT 0,
  owner TEXT,
  lease_until REAL,
  last_error TEXT,
  updated_at REAL NOT NULL,
  UNIQUE(post_id, stage)
);
CREATE INDEX IF NOT EXISTS idx_tasks_claim ON tasks(stage, status, available_at);
CREATE INDEX IF NOT EXISTS idx_tasks_expired ON tasks(status, lease_until);
CREATE TABLE IF NOT EXISTS crawl_checkpoints (
  category_id TEXT PRIMARY KEY REFERENCES categories(category_id),
  next_page INTEGER NOT NULL DEFAULT 1,
  complete INTEGER NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id TEXT NOT NULL REFERENCES reports(post_id),
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  media_type TEXT NOT NULL,
  UNIQUE(post_id, path)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  type TEXT NOT NULL,
  post_id TEXT,
  stage TEXT,
  details TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_post ON events(post_id, id);
"""


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
            self.conn.executescript(SCHEMA)

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
