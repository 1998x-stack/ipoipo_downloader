"""Tests for storage module."""
import unittest
import tempfile
import os
import json
from pathlib import Path
from storage import Storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = Storage(self.temp_dir)

    def tearDown(self):
        self.storage.close()
        for f in Path(self.temp_dir).glob("*.jsonl"):
            f.unlink()
        os.rmdir(self.temp_dir)

    def _append_report(self, **kwargs):
        self.storage.append("reports", kwargs)

    def test_append_and_read(self):
        self._append_report(type="report_found", post_id="1", title="Test")
        self.storage.close()
        lines = list(self.storage._read_lines("reports"))
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["post_id"], "1")

    def test_get_state_returns_last_event(self):
        self._append_report(type="report_found", post_id="1", title="Test")
        self._append_report(type="url_found", post_id="1", download_url="http://x.zip")
        self.storage.close()
        state = self.storage.get_state("reports", "1")
        self.assertEqual(state["type"], "url_found")
        self.assertEqual(state["download_url"], "http://x.zip")

    def test_query_by_status_pending(self):
        self._append_report(type="report_found", post_id="1", title="A", category_id="85")
        self._append_report(type="report_found", post_id="2", title="B", category_id="85")
        self._append_report(type="url_found", post_id="2", download_url="http://x.zip")
        self.storage.close()
        pending = self.storage.query_by_status("reports", "pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["post_id"], "1")

    def test_query_by_status_ready(self):
        self._append_report(type="report_found", post_id="1", title="A")
        self._append_report(type="url_found", post_id="1", download_url="http://x.zip")
        self.storage.close()
        ready = self.storage.query_by_status("reports", "ready")
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["post_id"], "1")

    def test_query_by_status_failed(self):
        self._append_report(type="report_found", post_id="1", title="A")
        self._append_report(type="url_found", post_id="1", download_url="http://x.zip")
        self._append_report(type="download_failed", post_id="1", error="403")
        self.storage.close()
        failed = self.storage.query_by_status("reports", "failed")
        self.assertEqual(len(failed), 1)

    def test_query_by_status_downloaded(self):
        self._append_report(type="report_found", post_id="1", title="A")
        self._append_report(type="url_found", post_id="1", download_url="http://x.zip")
        self._append_report(type="download_completed", post_id="1", file_path="/x.pdf")
        self.storage.close()
        downloaded = self.storage.query_by_status("reports", "downloaded")
        self.assertEqual(len(downloaded), 1)

    def test_get_stats(self):
        self._append_report(type="report_found", post_id="1", title="A", category_id="85")
        self._append_report(type="report_found", post_id="2", title="B", category_id="7")
        self._append_report(type="url_found", post_id="1", download_url="http://x.zip")
        self.storage.close()
        stats = self.storage.get_stats()
        self.assertEqual(stats["total_reports"], 2)
        self.assertIn("by_status", stats)

    def test_dedup_on_startup(self):
        self._append_report(type="report_found", post_id="1", title="A")
        self.storage.close()
        # Create new storage instance — should dedup from file
        storage2 = Storage(self.temp_dir)
        self._append_report.__func__(self, type="report_found", post_id="1", title="Updated")
        storage2.close()
        lines = list(storage2._read_lines("reports"))
        # Should have 2 lines (append-only), but get_state returns latest
        state = storage2.get_state("reports", "1")
        self.assertEqual(state["title"], "Updated")


if __name__ == "__main__":
    unittest.main()
