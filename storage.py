"""JSONL storage: append-only event log with state derivation."""
import json
import os
import threading
from pathlib import Path
from typing import Optional


# Event type → derived status mapping
STATUS_MAP = {
    "report_found": "pending",
    "url_found": "ready",
    "download_started": "downloading",
    "download_completed": "downloaded",
    "download_failed": "failed",
}

FILE_NAMES = {
    "categories": "categories.jsonl",
    "reports": "reports.jsonl",
    "downloads": "downloads.jsonl",
}


class Storage:
    """JSONL storage with append, read, dedup, and query by status."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._files = {}  # file_key → file handle
        self._seen_ids = {}  # file_key → set of IDs
        self._lock = threading.Lock()
        self._progress_path = self.data_dir / "progress.json"
        self._progress = self._load_progress()

    def _file_path(self, file_key: str) -> Path:
        return self.data_dir / FILE_NAMES.get(file_key, f"{file_key}.jsonl")

    def _get_handle(self, file_key: str):
        if file_key not in self._files:
            path = self._file_path(file_key)
            self._files[file_key] = open(path, "a", encoding="utf-8")
        return self._files[file_key]

    def _load_seen_ids(self, file_key: str):
        if file_key in self._seen_ids:
            return
        self._seen_ids[file_key] = set()
        path = self._file_path(file_key)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "post_id" in data:
                            self._seen_ids[file_key].add(data["post_id"])
                        elif "category_id" in data:
                            self._seen_ids[file_key].add(data["category_id"])
                    except json.JSONDecodeError:
                        continue

    def append(self, file_key: str, data: dict):
        """Append an event to the JSONL file."""
        with self._lock:
            self._load_seen_ids(file_key)
            handle = self._get_handle(file_key)
            handle.write(json.dumps(data, ensure_ascii=False) + "\n")
            handle.flush()
            if "post_id" in data:
                self._seen_ids[file_key].add(data["post_id"])
            elif "category_id" in data:
                self._seen_ids[file_key].add(data["category_id"])

    def _read_lines(self, file_key: str):
        """Read all lines from a JSONL file."""
        path = self._file_path(file_key)
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [line for line in f.readlines() if line.strip()]

    def get_state(self, file_key: str, entity_id: str) -> Optional[dict]:
        """Get the last event state for an entity."""
        with self._lock:
            lines = self._read_lines(file_key)
        last_state = None
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("post_id") == entity_id or data.get("category_id") == entity_id:
                    last_state = data
            except json.JSONDecodeError:
                continue
        return last_state

    def query_by_status(self, file_key: str, status: str) -> list:
        """Query all entities with a given derived status."""
        with self._lock:
            lines = self._read_lines(file_key)
            cat_lines = self._read_lines("categories")
        # Build category name lookup
        cat_names = {}
        for line in cat_lines:
            try:
                data = json.loads(line)
                if "category_id" in data:
                    cat_names[data["category_id"]] = data.get("category_name", "")
            except json.JSONDecodeError:
                continue
        states = {}
        for line in lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    pid = data["post_id"]
                    if pid not in states:
                        states[pid] = {}
                    states[pid].update(data)
            except json.JSONDecodeError:
                continue

        results = []
        for post_id, state in states.items():
            derived = STATUS_MAP.get(state.get("type", ""), "")
            if derived == status:
                # Backfill category_name if missing
                if "category_name" not in state and "category_id" in state:
                    state["category_name"] = cat_names.get(state["category_id"], "")
                results.append(state)
        return results

    def get_reports_by_category(self, category_id: str) -> list:
        """Get all reports for a category (latest state per post_id)."""
        with self._lock:
            lines = self._read_lines("reports")
        states = {}
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("category_id") == category_id and "post_id" in data:
                    states[data["post_id"]] = data
            except json.JSONDecodeError:
                continue
        return list(states.values())

    def get_category_report_count(self, category_id: str) -> int:
        """Count unique reports for a category."""
        with self._lock:
            lines = self._read_lines("reports")
        post_ids = set()
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("category_id") == category_id and "post_id" in data:
                    post_ids.add(data["post_id"])
            except json.JSONDecodeError:
                continue
        return len(post_ids)

    def is_report_downloaded(self, post_id: str) -> bool:
        """Check if a report has been successfully downloaded."""
        state = self.get_state("reports", post_id)
        return state is not None and state.get("type") == "download_completed"

    def get_stats(self) -> dict:
        """Get overall statistics."""
        with self._lock:
            cat_lines = self._read_lines("categories")
            report_lines = self._read_lines("reports")
            dl_lines = self._read_lines("downloads")
        stats = {"total_categories": 0, "total_reports": 0, "total_downloads": 0, "by_status": {}}

        # Categories
        stats["total_categories"] = len(cat_lines)

        # Reports
        states = {}
        for line in report_lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    states[data["post_id"]] = data
            except json.JSONDecodeError:
                continue
        stats["total_reports"] = len(states)

        # Count by status
        status_counts = {}
        for state in states.values():
            derived = STATUS_MAP.get(state.get("type", ""), "unknown")
            status_counts[derived] = status_counts.get(derived, 0) + 1
        stats["by_status"] = status_counts

        # Downloads (count unique post_ids)
        dl_ids = set()
        for line in dl_lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    dl_ids.add(data["post_id"])
            except json.JSONDecodeError:
                continue
        stats["total_downloads"] = len(dl_ids)

        return stats

    def _load_progress(self) -> dict:
        if self._progress_path.exists():
            try:
                return json.loads(self._progress_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def save_progress(self, category_id: str, page: int):
        with self._lock:
            self._progress[category_id] = page
            self._progress_path.write_text(json.dumps(self._progress))

    def get_progress(self, category_id: str) -> int:
        return self._progress.get(category_id, 0)

    def close(self):
        """Close all file handles."""
        for f in self._files.values():
            f.close()
        self._files.clear()
