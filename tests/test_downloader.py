"""Tests for downloader module."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import zipfile
from pathlib import Path
from downloader import Downloader
from storage import Storage
from logger import Logger


class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = Storage(self.temp_dir)
        self.log = Logger("test_downloader")
        self.downloader = Downloader(self.storage, self.log, use_proxy=False)

    def tearDown(self):
        self.storage.close()
        self.log.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_download_page_url(self):
        url = self.downloader.get_download_page_url("26028")
        self.assertEqual(url, "https://ipoipo.cn/download/26028.html")

    def test_get_category_dir(self):
        path = self.downloader.get_category_dir("85", "人工智能AI行业")
        self.assertTrue(str(path).endswith("85_人工智能AI行业"))

    def test_generate_filename(self):
        name = self.downloader.generate_filename("202512021157134086066.zip", "测试报告")
        self.assertTrue(name.startswith("20251202_"))
        self.assertTrue(name.endswith(".pdf"))

    @patch.object(Downloader, "_download_zip")
    def test_download_report_emits_event(self, mock_download):
        mock_download.return_value = (True, "/tmp/test.pdf", 1000)
        self.storage.append("reports", {
            "type": "report_found", "post_id": "1", "title": "Test", "category_id": "85"
        })
        self.storage.append("reports", {
            "type": "url_found", "post_id": "1", "download_url": "http://x.zip"
        })
        self.storage.close()
        storage2 = Storage(self.temp_dir)
        dl = Downloader(storage2, self.log, use_proxy=False)
        ready = storage2.query_by_status("reports", "ready")
        self.assertEqual(len(ready), 1)
        storage2.close()


if __name__ == "__main__":
    unittest.main()
