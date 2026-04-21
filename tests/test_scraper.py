"""Tests for scraper module."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from scraper import Scraper
from storage import Storage
from logger import Logger


class TestScraper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = Storage(self.temp_dir)
        self.log = Logger("test_scraper")
        self.scraper = Scraper(self.storage, self.log, use_proxy=False)

    def tearDown(self):
        self.storage.close()
        self.log.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("scraper.requests.Session")
    def test_parse_report_card(self, mock_session):
        html = """
        <div class="wapost card">
            <h2 class="multi-ellipsis"><a href="https://ipoipo.cn/post/26028.html" title="Test Report">Test Report</a></h2>
            <p class="img"><a><img class="img-cover br" src="https://img.jpg"></a></p>
            <p class="text">Description text</p>
            <div class="count">
                <span class="view-num"><i class="fa fa-eye"></i>44</span>
                <span class="edit"><i class="fa fa-clock-o"></i>2025-12-22</span>
            </div>
        </div>
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        card = soup.find("div", class_="wapost card")
        result = self.scraper.parse_report_card(card)
        self.assertEqual(result["post_id"], "26028")
        self.assertEqual(result["title"], "Test Report")
        self.assertEqual(result["detail_url"], "https://ipoipo.cn/post/26028.html")
        self.assertEqual(result["view_count"], 44)
        self.assertEqual(result["publish_date"], "2025-12-22")

    def test_parse_report_card_missing_h2_returns_none(self):
        html = '<div class="wapost card"><p>No title</p></div>'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        card = soup.find("div", class_="wapost card")
        result = self.scraper.parse_report_card(card)
        self.assertIsNone(result)

    @patch.object(Scraper, "scrape_page")
    def test_scrape_category_emits_events(self, mock_scrape_page):
        mock_scrape_page.return_value = [
            {"post_id": "1", "title": "Report 1", "detail_url": "https://ipoipo.cn/post/1.html",
             "thumbnail_url": "", "view_count": 0, "publish_date": "2025-01-01"}
        ]
        self.scraper.scrape_category("85", "AI", max_pages=1)
        self.storage.close()
        state = self.storage.get_state("reports", "1")
        self.assertIsNotNone(state)
        self.assertEqual(state["type"], "report_found")


if __name__ == "__main__":
    unittest.main()
