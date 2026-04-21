"""Tests for utils modules."""
import unittest
from utils.headers import get_browser_headers, get_download_headers
from utils.sanitize import clean_filename, clean_foldername, extract_timestamp_from_zip, generate_doc_filename
from utils.helpers import sleep_jitter, is_valid_url


class TestHeaders(unittest.TestCase):
    def test_default_headers_has_user_agent(self):
        headers = get_browser_headers()
        self.assertIn("User-Agent", headers)
        self.assertIn("Chrome", headers["User-Agent"])

    def test_headers_with_referer(self):
        headers = get_browser_headers(referer="https://example.com")
        self.assertEqual(headers["Referer"], "https://example.com")
        self.assertEqual(headers["Sec-Fetch-Site"], "cross-site")

    def test_headers_without_referer(self):
        headers = get_browser_headers()
        self.assertNotIn("Referer", headers)
        self.assertEqual(headers["Sec-Fetch-Site"], "none")

    def test_download_headers_requires_referer(self):
        headers = get_download_headers("https://ipoipo.cn/download/123.html")
        self.assertEqual(headers["Referer"], "https://ipoipo.cn/download/123.html")
        self.assertEqual(headers["Sec-Fetch-Site"], "cross-site")


class TestSanitize(unittest.TestCase):
    def test_clean_filename_removes_chinese_punctuation(self):
        result = clean_filename("报告【测试】（重要）")
        self.assertNotIn("【", result)
        self.assertNotIn("】", result)
        self.assertNotIn("（", result)
        self.assertNotIn("）", result)

    def test_clean_filename_preserves_extension(self):
        result = clean_filename("test_report.pdf")
        self.assertTrue(result.endswith(".pdf"))

    def test_clean_filename_collapses_underscores(self):
        result = clean_filename("test___report")
        self.assertNotIn("___", result)

    def test_clean_filename_max_length(self):
        long_name = "a" * 300 + ".pdf"
        result = clean_filename(long_name)
        self.assertLessEqual(len(result), 200)

    def test_clean_foldername_stricter(self):
        result = clean_foldername("test【report】（2025）")
        self.assertRegex(result, r"^[\w\u4e00-\u9fff_]+$")

    def test_extract_timestamp_from_zip(self):
        result = extract_timestamp_from_zip("202512021157134086066.zip")
        self.assertEqual(result, "20251202")

    def test_extract_timestamp_fallback(self):
        result = extract_timestamp_from_zip("no_date.zip")
        self.assertEqual(len(result), 8)

    def test_generate_doc_filename(self):
        result = generate_doc_filename("202512021157134086066.zip", "测试报告")
        self.assertTrue(result.startswith("20251202_"))


class TestHelpers(unittest.TestCase):
    def test_sleep_jitter_no_exception(self):
        sleep_jitter(0.01, 0.02)

    def test_is_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com/path"))
        self.assertFalse(is_valid_url("not-a-url"))
        self.assertFalse(is_valid_url(""))


if __name__ == "__main__":
    unittest.main()
