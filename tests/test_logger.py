"""Tests for logger module."""
import unittest
import json
import tempfile
import os
from logger import Logger


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.temp_log = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode="w")
        self.temp_log.close()
        self.logger = Logger(module_name="test", jsonl_path=self.temp_log.name)

    def tearDown(self):
        self.logger.close()
        if os.path.exists(self.temp_log.name):
            os.remove(self.temp_log.name)

    def test_info_logs_to_file(self):
        self.logger.info("test message", key="value")
        self.logger.close()
        with open(self.temp_log.name) as f:
            lines = [l for l in f.readlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["module"], "test")
        self.assertEqual(entry["msg"], "test message")
        self.assertEqual(entry["key"], "value")

    def test_ok_logs_to_file(self):
        self.logger.ok("success message")
        self.logger.close()
        with open(self.temp_log.name) as f:
            lines = [l for l in f.readlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["level"], "ok")

    def test_warn_logs_to_file(self):
        self.logger.warn("warning message")
        self.logger.close()
        with open(self.temp_log.name) as f:
            lines = [l for l in f.readlines() if l.strip()]
        entry = json.loads(lines[0])
        self.assertEqual(entry["level"], "warn")

    def test_error_logs_to_file(self):
        self.logger.error("error message")
        self.logger.close()
        with open(self.temp_log.name) as f:
            lines = [l for l in f.readlines() if l.strip()]
        entry = json.loads(lines[0])
        self.assertEqual(entry["level"], "error")

    def test_all_kwargs_in_json(self):
        self.logger.info("test", foo="bar", count=42)
        self.logger.close()
        with open(self.temp_log.name) as f:
            entry = json.loads(f.read().strip())
        self.assertEqual(entry["foo"], "bar")
        self.assertEqual(entry["count"], 42)


if __name__ == "__main__":
    unittest.main()
