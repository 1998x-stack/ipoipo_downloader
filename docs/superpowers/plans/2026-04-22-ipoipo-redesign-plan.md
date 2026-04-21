# ipoipo Downloader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete ipoipo.cn report scraper from scratch with JSONL storage, dual-output logging, domain-driven modules, and sequential execution with auto proxy-switch.

**Architecture:** Event-driven pipeline. Each domain module (scraper, downloader) emits events that storage.py appends to JSONL files. Status is derived from last event per entity. Sequential execution with auto proxy-switch on failure.

**Tech Stack:** Python 3.10+, requests, beautifulsoup4, lxml, PyYAML, unittest

---

## File Structure

| File | Responsibility |
|------|---------------|
| `config.py` | All constants: URLs, delays, category mappings, path setup |
| `.gitignore` | Ignore data/, logs/, __pycache__/, .env, *.pyc |
| `utils/__init__.py` | Package marker |
| `utils/headers.py` | Browser header generation |
| `utils/sanitize.py` | Filename cleaning, timestamp extraction |
| `utils/helpers.py` | retry decorator, jitter sleep, URL helpers |
| `tests/test_utils.py` | Tests for all utils |
| `logger.py` | Dual-output logger (console + JSON file) |
| `tests/test_logger.py` | Logger tests |
| `storage.py` | JSONL append, read, dedup, query by status |
| `tests/test_storage.py` | Storage tests |
| `proxy.py` | Clash YAML parsing, node testing, auto-switch |
| `tests/test_proxy.py` | Proxy tests |
| `scraper.py` | Stage 1-3: categories, report lists, download URLs |
| `tests/test_scraper.py` | Scraper tests |
| `downloader.py` | Stage 4: ZIP download, extract, rename |
| `tests/test_downloader.py` | Downloader tests |
| `main.py` | CLI entry point, argparse, pipeline orchestration |
| `scripts/run.sh` | Full pipeline background runner |
| `scripts/run_stage.sh` | Single stage runner |
| `scripts/stats.sh` | JSONL stats summary |
| `README.md` | Setup, usage, architecture docs |
| `requirements.txt` | Python dependencies |
| `config/proxy.yaml` | Clash proxy config (copy from old codebase) |

---

### Task 1: Config + .gitignore

**Files:**
- Create: `config.py`
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `config/proxy.yaml`

- [ ] **Step 1: Write .gitignore**

```
__pycache__/
*.pyc
*.pyo
data/
logs/
.env
*.egg-info/
dist/
build/
.DS_Store
```

- [ ] **Step 2: Write requirements.txt**

```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
PyYAML>=6.0
```

- [ ] **Step 3: Write config.py**

```python
"""Configuration for ipoipo downloader."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
LOG_DIR = BASE_DIR / "logs"

for d in [DATA_DIR, DOWNLOAD_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Website URLs
BASE_URL = "https://ipoipo.cn"
CATEGORY_PAGE_URL = "https://ipoipo.cn/tags-{}.html"
CATEGORY_PAGE_PAGINATED = "https://ipoipo.cn/tags-{}_{}.html"
POST_URL = "https://ipoipo.cn/post/{}.html"
DOWNLOAD_URL = "https://ipoipo.cn/download/{}.html"
ZIP_HOST = "https://ipo.ai-tag.cn"

# Category mappings (ID -> name)
CATEGORY_NAMES = {
    "70": "TMT行业",
    "53": "医药医疗器械行业",
    "59": "金融行业",
    "69": "新能源及电力行业",
    "14": "电子行业",
    "10": "智能制造行业",
    "79": "汽车行业",
    "67": "地产及旅游行业",
    "34": "经济报告",
    "24": "新材料及矿产报告",
    "61": "电商及销售报告",
    "62": "消费者及人群研究报告",
    "33": "食品饮料酒水行业",
    "11": "大消费报告",
    "85": "人工智能AI行业",
    "60": "化工行业",
    "63": "物流行业",
    "7": "教育行业",
    "23": "云计算行业",
    "56": "节能环保行业",
    "64": "农林牧渔行业",
    "73": "餐饮业报告",
    "74": "化妆品行业",
    "25": "体育及用品行业",
    "68": "军工行业",
    "76": "光电行业",
    "39": "纺织服装行业",
    "86": "航天通讯行业",
    "77": "安全监控行业",
    "66": "服务业报告",
    "84": "宠物行业",
    "75": "奢侈品及珠宝报告",
    "72": "经验干货",
    "83": "母婴行业",
    "80": "检测行业报告",
    "82": "共享经济报告",
    "88": "新基建报告",
    "54": "博彩行业报告",
}

# Request settings
REQUEST_DELAY = (1, 3)
MAX_RETRIES = 3
RETRY_DELAY = 1.5
DOWNLOAD_TIMEOUT = 300
REQUEST_TIMEOUT = 30

# Proxy settings
PROXY_CONFIG_PATH = BASE_DIR / "config" / "proxy.yaml"
PROXY_TEST_TIMEOUT = 3
PROXY_MAX_LATENCY = 500
USE_PROXY = True

# Download settings
CHUNK_SIZE = 8192
KEEP_ZIP = False
MAX_FILENAME_LENGTH = 200
MIN_VALID_FILE_SIZE = 1024  # bytes

# Logging
LOG_FILE = LOG_DIR / "events.jsonl"
```

- [ ] **Step 4: Copy proxy.yaml**

Copy `config/clash_config.yaml` from the `main` branch to `config/proxy.yaml`:
```bash
git show main:config/clash_config.yaml > config/proxy.yaml
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt config.py config/proxy.yaml
git commit -m "feat: add config, .gitignore, requirements, proxy.yaml"
```

---

### Task 2: Utils

**Files:**
- Create: `utils/__init__.py`
- Create: `utils/headers.py`
- Create: `utils/sanitize.py`
- Create: `utils/helpers.py`
- Create: `tests/__init__.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Create utils/__init__.py**

```python
"""Shared utilities."""
```

- [ ] **Step 2: Create utils/headers.py**

```python
"""Browser header generation."""

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def get_browser_headers(referer: str = None) -> dict:
    """Return browser headers, optionally with Referer."""
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


def get_download_headers(referer: str) -> dict:
    """Return headers for ZIP download (must have Referer)."""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
```

- [ ] **Step 3: Create utils/sanitize.py**

```python
"""Filename sanitization and timestamp extraction."""
import re
from datetime import datetime
from pathlib import Path


ILLEGAL_CHARS = r'[<>:"/\\|?*【】（）《》""''：；，。！？\[\]]'


def clean_filename(name: str, max_length: int = 200) -> str:
    """Clean a filename, preserving extension."""
    path = Path(name)
    stem = path.stem
    ext = path.suffix

    stem = re.sub(ILLEGAL_CHARS, "_", stem)
    stem = stem.replace("（", "_").replace("）", "_")
    stem = stem.replace("【", "_").replace("】", "_")
    stem = re.sub(r"[_\s.]+", "_", stem)
    stem = stem.strip("_. ")

    if not stem:
        stem = "unnamed"

    max_stem = max_length - len(ext)
    if len(stem) > max_stem:
        stem = stem[:max_stem]

    return stem + ext


def clean_foldername(name: str) -> str:
    """Clean a folder name (stricter than filename)."""
    name = re.sub(ILLEGAL_CHARS, "_", name)
    name = name.replace("（", "_").replace("）", "_")
    name = name.replace("【", "_").replace("】", "_")
    name = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_ ")
    return name or "unnamed"


def extract_timestamp_from_zip(filename: str) -> str:
    """Extract YYYYMMDD from ZIP filename like 202512021157134086066.zip."""
    patterns = [
        r"^(\d{8})",
        r"(\d{8})_",
        r"_(\d{8})",
        r"(\d{14})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            ts = match.group(1)[:8]
            try:
                datetime.strptime(ts, "%Y%m%d")
                return ts
            except ValueError:
                continue
    return datetime.now().strftime("%Y%m%d")


def generate_doc_filename(zip_filename: str, report_title: str, publish_date: str = None) -> str:
    """Generate final document filename: YYYYMMDD_sanitized_title.ext."""
    ts = extract_timestamp_from_zip(zip_filename)
    ext = Path(zip_filename).suffix.replace(".zip", "")
    if not ext:
        ext = ".pdf"  # default

    clean_title = clean_filename(report_title)
    clean_title = clean_title.replace(".", "_").replace(" ", "")
    clean_title = clean_title.strip()

    return f"{ts}_{clean_title}{ext}"
```

- [ ] **Step 4: Create utils/helpers.py**

```python
"""Common helpers: retry, jitter sleep, URL helpers."""
import time
import random
import functools
from urllib.parse import urljoin, urlparse


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        return wrapper
    return decorator


def sleep_jitter(low: float, high: float):
    """Sleep for a random duration between low and high seconds."""
    time.sleep(random.uniform(low, high))


def extract_post_id(url: str) -> str:
    """Extract post_id from URL like https://ipoipo.cn/post/26028.html."""
    match = re.search(r"/post/(\d+)\.html", url)
    return match.group(1) if match else ""


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


import re  # needed for extract_post_id
```

- [ ] **Step 5: Create tests/__init__.py**

```python
"""Tests."""
```

- [ ] **Step 6: Create tests/test_utils.py**

```python
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
        # Should only contain word chars, Chinese chars, underscores
        self.assertRegex(result, r"^[\w\u4e00-\u9fff_]+$")

    def test_extract_timestamp_from_zip(self):
        result = extract_timestamp_from_zip("202512021157134086066.zip")
        self.assertEqual(result, "20251202")

    def test_extract_timestamp_fallback(self):
        result = extract_timestamp_from_zip("no_date.zip")
        self.assertEqual(len(result), 8)  # Returns current date

    def test_generate_doc_filename(self):
        result = generate_doc_filename("202512021157134086066.zip", "测试报告")
        self.assertTrue(result.startswith("20251202_"))


class TestHelpers(unittest.TestCase):
    def test_sleep_jitter_no_exception(self):
        sleep_jitter(0.01, 0.02)  # Should not raise

    def test_is_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com/path"))
        self.assertFalse(is_valid_url("not-a-url"))
        self.assertFalse(is_valid_url(""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 7: Run tests**

```bash
python -m unittest tests/test_utils.py -v
```
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add utils/ tests/test_utils.py
git commit -m "feat: add utils (headers, sanitize, helpers) with tests"
```

---

### Task 3: Logger

**Files:**
- Create: `logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_logger.py`:

```python
"""Tests for logger module."""
import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m unittest tests/test_logger.py -v
```
Expected: FAIL — ModuleNotFoundError: No module named 'logger'

- [ ] **Step 3: Write logger.py**

```python
"""Dual-output logger: colored console + structured JSON file."""
import json
import sys
from datetime import datetime
from pathlib import Path


class Logger:
    """Logger with colored console output and JSONL file output."""

    COLORS = {
        "info": "\033[34m",    # blue
        "ok": "\033[32m",      # green
        "warn": "\033[33m",    # yellow
        "error": "\033[31m",   # red
        "reset": "\033[0m",
    }

    LEVEL_LABELS = {
        "info": "INFO",
        "ok": "OK",
        "warn": "WARN",
        "error": "ERROR",
    }

    def __init__(self, module_name: str, jsonl_path: str = None):
        self.module_name = module_name
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        if self.jsonl_path:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.jsonl_path, "a", encoding="utf-8")
        else:
            self._file = None

    def _format_console(self, level: str, msg: str, **kwargs) -> str:
        color = self.COLORS.get(level, "")
        reset = self.COLORS["reset"]
        label = self.LEVEL_LABELS.get(level, level).upper()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} [{label:<5}] {self.module_name:<12} {msg}"

    def _write_json(self, level: str, msg: str, **kwargs):
        if not self._file:
            return
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": level,
            "module": self.module_name,
            "msg": msg,
        }
        entry.update(kwargs)
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def _log(self, level: str, msg: str, **kwargs):
        console_msg = self._format_console(level, msg, **kwargs)
        print(f"{self.COLORS.get(level, '')}{console_msg}{self.COLORS['reset']}", flush=True)
        self._write_json(level, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log("info", msg, **kwargs)

    def ok(self, msg: str, **kwargs):
        self._log("ok", msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self._log("warn", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log("error", msg, **kwargs)

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


def get_logger(module_name: str, jsonl_path: str = None) -> Logger:
    """Get a logger instance."""
    return Logger(module_name, jsonl_path)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m unittest tests/test_logger.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add logger.py tests/test_logger.py
git commit -m "feat: add dual-output logger (console + JSONL) with tests"
```

---

### Task 4: Storage

**Files:**
- Create: `storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m unittest tests/test_storage.py -v
```
Expected: FAIL — ModuleNotFoundError: No module named 'storage'

- [ ] **Step 3: Write storage.py**

```python
"""JSONL storage: append-only event log with state derivation."""
import json
import os
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
        lines = self._read_lines(file_key)
        # Group by post_id, keep last event
        states = {}
        for line in lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    states[data["post_id"]] = data
            except json.JSONDecodeError:
                continue

        results = []
        for post_id, state in states.items():
            derived = STATUS_MAP.get(state.get("type", ""), "")
            if derived == status:
                results.append(state)
        return results

    def get_stats(self) -> dict:
        """Get overall statistics."""
        stats = {"total_categories": 0, "total_reports": 0, "total_downloads": 0, "by_status": {}}

        # Categories
        cat_lines = self._read_lines("categories")
        stats["total_categories"] = len(cat_lines)

        # Reports
        report_lines = self._read_lines("reports")
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

        # Downloads
        dl_lines = self._read_lines("downloads")
        stats["total_downloads"] = len(dl_lines)

        return stats

    def close(self):
        """Close all file handles."""
        for f in self._files.values():
            f.close()
        self._files.clear()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m unittest tests/test_storage.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add storage.py tests/test_storage.py
git commit -m "feat: add JSONL storage with state derivation and tests"
```

---

### Task 5: Proxy

**Files:**
- Create: `proxy.py`
- Create: `tests/test_proxy.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_proxy.py`:

```python
"""Tests for proxy module."""
import unittest
import tempfile
import os
from proxy import ProxyManager


class TestProxyManager(unittest.TestCase):
    def setUp(self):
        self.temp_config = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w")
        self.temp_config.write("""
mixed-port: 7890
proxies:
  - {name: 'HK 01', type: ss, server: hk.example.com, port: 1234, cipher: aes-128-gcm, password: test}
  - {name: 'JP 01', type: ss, server: jp.example.com, port: 5678, cipher: aes-128-gcm, password: test}
""")
        self.temp_config.close()
        self.pm = ProxyManager(self.temp_config.name)

    def tearDown(self):
        if os.path.exists(self.temp_config.name):
            os.remove(self.temp_config.name)

    def test_loads_nodes(self):
        self.assertEqual(len(self.pm.nodes), 2)

    def test_parses_mixed_port(self):
        self.assertEqual(self.pm.local_port, 7890)

    def test_get_local_proxy(self):
        proxy = self.pm.get_local_proxy()
        self.assertEqual(proxy["http"], "http://127.0.0.1:7890")
        self.assertEqual(proxy["https"], "http://127.0.0.1:7890")

    def test_select_random_returns_node(self):
        node = self.pm.select_random()
        self.assertIsNotNone(node)
        self.assertIn(node.name, ["HK 01", "JP 01"])

    def test_mark_node_failed(self):
        node = self.pm.nodes[0]
        self.pm.mark_node_failed(node)
        self.assertEqual(node.fail_count, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m unittest tests/test_proxy.py -v
```
Expected: FAIL — ModuleNotFoundError: No module named 'proxy'

- [ ] **Step 3: Write proxy.py**

```python
"""Proxy manager: Clash YAML parsing, node testing, auto-switch."""
import yaml
import socket
import random
import time
from typing import List, Optional, Dict
from dataclasses import dataclass
from logger import get_logger


@dataclass
class ProxyNode:
    name: str
    server: str
    port: int
    type: str
    latency: float = float("inf")
    fail_count: int = 0


class ProxyManager:
    def __init__(self, config_path: str, local_port: int = 7890, max_latency: int = 500):
        self.config_path = config_path
        self.local_port = local_port
        self.max_latency = max_latency
        self.nodes: List[ProxyNode] = []
        self.current_node: Optional[ProxyNode] = None
        self.log = get_logger("proxy")
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "mixed-port" in config:
                self.local_port = config["mixed-port"]
            for proxy in config.get("proxies", []):
                if proxy.get("type") == "ss":
                    node = ProxyNode(
                        name=proxy["name"],
                        server=proxy["server"],
                        port=proxy["port"],
                        type=proxy["type"],
                    )
                    self.nodes.append(node)
            self.log.info(f"Loaded {len(self.nodes)} proxy nodes from {self.config_path}")
        except Exception as e:
            self.log.error(f"Failed to load proxy config: {e}")
            raise

    def test_node(self, node: ProxyNode, timeout: float = 3.0) -> float:
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((node.server, node.port))
            latency = (time.time() - start) * 1000
            sock.close()
            node.latency = latency
            return latency
        except Exception:
            node.latency = float("inf")
            node.fail_count += 1
            return float("inf")

    def test_all_nodes(self, max_workers: int = 10):
        self.log.info(f"Testing {len(self.nodes)} nodes...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.test_node, n): n for n in self.nodes}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(f"Node test failed: {e}")
        self.nodes.sort(key=lambda n: n.latency)
        available = [n for n in self.nodes if n.latency < float("inf")]
        self.log.info(f"Available nodes: {len(available)}/{len(self.nodes)}")

    def select_random(self, max_latency: int = None) -> ProxyNode:
        threshold = max_latency or self.max_latency
        available = [n for n in self.nodes if n.latency < threshold and n.fail_count < 3]
        if not available:
            self.log.warn("No nodes meet latency threshold, selecting fastest")
            return self._select_fastest()
        node = random.choice(available)
        self.current_node = node
        self.log.info(f"Selected node: {node.name} ({node.latency:.0f}ms)")
        return node

    def _select_fastest(self) -> ProxyNode:
        available = [n for n in self.nodes if n.latency < float("inf")]
        if not available:
            raise RuntimeError("No available proxy nodes")
        fastest = min(available, key=lambda n: n.latency)
        self.current_node = fastest
        self.log.info(f"Selected fastest node: {fastest.name} ({fastest.latency:.0f}ms)")
        return fastest

    def get_local_proxy(self) -> Dict[str, str]:
        return {
            "http": f"http://127.0.0.1:{self.local_port}",
            "https": f"http://127.0.0.1:{self.local_port}",
        }

    def mark_node_failed(self, node: ProxyNode):
        node.fail_count += 1
        self.log.warn(f"Node failed: {node.name} (failures: {node.fail_count})")

    def switch_node(self) -> bool:
        if self.current_node:
            self.mark_node_failed(self.current_node)
        try:
            new_node = self.select_random()
            return True
        except RuntimeError:
            self.log.error("No nodes available for switch")
            return False
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m unittest tests/test_proxy.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add proxy.py tests/test_proxy.py
git commit -m "feat: add proxy manager with Clash parsing and tests"
```

---

### Task 6: Scraper

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m unittest tests/test_scraper.py -v
```
Expected: FAIL — ModuleNotFoundError: No module named 'scraper'

- [ ] **Step 3: Write scraper.py**

```python
"""Scraper: Stage 1-3 — categories, report lists, download URLs."""
import re
import time
import random
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import requests
from config import (
    CATEGORY_NAMES, CATEGORY_PAGE_URL, CATEGORY_PAGE_PAGINATED,
    DOWNLOAD_URL, REQUEST_DELAY, REQUEST_TIMEOUT, MAX_RETRIES,
    USE_PROXY, PROXY_CONFIG_PATH,
)
from utils.headers import get_browser_headers
from utils.helpers import sleep_jitter


class Scraper:
    def __init__(self, storage, log, use_proxy: bool = USE_PROXY, proxy_manager=None):
        self.storage = storage
        self.log = log
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.session.headers.update(get_browser_headers())
        if use_proxy and proxy_manager:
            self.session.proxies.update(proxy_manager.get_local_proxy())

    def close(self):
        self.session.close()

    # ── Stage 1: Categories ──

    def scrape_all_categories(self) -> List[Dict]:
        self.log.info("Stage 1: Scraping categories")
        categories = []
        for cat_id, cat_name in CATEGORY_NAMES.items():
            url = CATEGORY_PAGE_URL.format(cat_id)
            self.storage.append("categories", {
                "type": "category",
                "category_id": cat_id,
                "category_name": cat_name,
                "url": url,
            })
            self.log.ok(f"category:{cat_id} {cat_name}")
            categories.append({"category_id": cat_id, "category_name": cat_name, "url": url})
        self.log.info(f"Total categories: {len(categories)}")
        return categories

    # ── Stage 2: Report Lists ──

    def scrape_page(self, url: str) -> List[Dict]:
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.find_all("div", class_="wapost card")
            reports = []
            for card in cards:
                report = self.parse_report_card(card)
                if report:
                    reports.append(report)
            return reports
        except Exception as e:
            self.log.error(f"Failed to scrape page: {url} — {e}")
            return []

    def parse_report_card(self, card) -> Optional[Dict]:
        try:
            h2 = card.find("h2", class_="multi-ellipsis")
            if not h2:
                return None
            link = h2.find("a")
            if not link:
                return None
            title = link.get("title", "").strip()
            detail_url = link.get("href", "").strip()
            match = re.search(r"/post/(\d+)\.html", detail_url)
            if not match:
                return None
            post_id = match.group(1)
            img = card.find("img", class_="img-cover")
            thumbnail_url = img.get("src", "") if img else ""
            text_p = card.find("p", class_="text")
            description = text_p.get_text(strip=True) if text_p else ""
            count_div = card.find("div", class_="count")
            view_count = 0
            publish_date = ""
            if count_div:
                view_span = count_div.find("span", class_="view-num")
                if view_span:
                    m = re.search(r"\d+", view_span.get_text(strip=True))
                    if m:
                        view_count = int(m.group())
                edit_span = count_div.find("span", class_="edit")
                if edit_span:
                    publish_date = edit_span.get_text(strip=True)
            return {
                "post_id": post_id,
                "title": title,
                "detail_url": detail_url,
                "thumbnail_url": thumbnail_url,
                "description": description,
                "view_count": view_count,
                "publish_date": publish_date,
            }
        except Exception as e:
            self.log.error(f"Failed to parse report card: {e}")
            return None

    def scrape_category(self, category_id: str, category_name: str, max_pages: int = None) -> List[Dict]:
        self.log.info(f"Stage 2: Scraping category:{category_id} {category_name}")
        all_reports = []
        page = 1
        while True:
            url = CATEGORY_PAGE_URL.format(category_id) if page == 1 else CATEGORY_PAGE_PAGINATED.format(category_id, page)
            self.log.info(f"  Page {page}: {url}")
            reports = self.scrape_page(url)
            if not reports:
                self.log.info(f"  Page {page} has no data, stopping")
                break
            for r in reports:
                self.storage.append("reports", {
                    "type": "report_found",
                    "post_id": r["post_id"],
                    "category_id": category_id,
                    "title": r["title"],
                    "detail_url": r["detail_url"],
                    "thumbnail_url": r["thumbnail_url"],
                    "view_count": r["view_count"],
                    "publish_date": r["publish_date"],
                })
                self.log.ok(f"  report:{r['post_id']} {r['title'][:40]}")
            all_reports.extend(reports)
            if max_pages and page >= max_pages:
                break
            page += 1
            sleep_jitter(*REQUEST_DELAY)
        self.log.info(f"  Total reports for {category_name}: {len(all_reports)}")
        return all_reports

    def scrape_all_categories(self, max_pages: int = None):
        categories = self.storage._read_lines("categories")
        if not categories:
            self.scrape_all_categories()
            categories = self.storage._read_lines("categories")
        import json
        for line in categories:
            cat = json.loads(line)
            self.scrape_category(cat["category_id"], cat["category_name"], max_pages=max_pages)

    # ── Stage 3: Download URLs ──

    def get_download_page_url(self, post_id: str) -> str:
        return DOWNLOAD_URL.format(post_id)

    def extract_zip_url(self, html: str, base_url: str = None) -> Optional[str]:
        from urllib.parse import urljoin
        soup = BeautifulSoup(html, "lxml")
        # Method 1: href ends with .zip
        links = soup.find_all("a", href=re.compile(r"\.zip$", re.I))
        if links:
            return urljoin(base_url, links[0].get("href")) if base_url else links[0].get("href")
        # Method 2: style with font-size + color
        links = soup.find_all("a", style=re.compile(r"font-size.*color"))
        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if ".zip" in href.lower() or ".zip" in text.lower():
                return urljoin(base_url, href) if base_url else href
        # Method 3: text contains .zip
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            if ".zip" in text.lower():
                href = link.get("href", "")
                if href:
                    return urljoin(base_url, href) if base_url else href
        # Method 4: regex
        matches = re.findall(r"https?://[^\s<>"']+.zip", html, re.I)
        if matches:
            return matches[0]
        return None

    def visit_download_page(self, post_id: str) -> tuple:
        url = self.get_download_page_url(post_id)
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return True, resp.text, url
        except Exception as e:
            self.log.error(f"Failed to visit download page for {post_id}: {e}")
            return False, None, url

    def process_pending_reports(self, limit: int = 100):
        self.log.info("Stage 3: Processing pending reports for download URLs")
        pending = self.storage.query_by_status("reports", "pending")
        if limit:
            pending = pending[:limit]
        self.log.info(f"  Pending reports: {len(pending)}")
        success = 0
        fail = 0
        for i, report in enumerate(pending):
            post_id = report["post_id"]
            title = report.get("title", "")
            self.log.info(f"  [{i+1}/{len(pending)}] {title[:40]}")
            ok, html, page_url = self.visit_download_page(post_id)
            if not ok or not html:
                fail += 1
                continue
            sleep_jitter(0.5, 1.0)
            zip_url = self.extract_zip_url(html, base_url=page_url)
            if zip_url:
                self.storage.append("reports", {
                    "type": "url_found",
                    "post_id": post_id,
                    "download_url": zip_url,
                })
                self.log.ok(f"  URL found: {post_id}")
                success += 1
            else:
                self.log.warn(f"  No ZIP URL for {post_id}")
                fail += 1
            if i < len(pending) - 1:
                sleep_jitter(1.5, 2.5)
        self.log.info(f"  Stage 3 complete: {success} success, {fail} failed")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m unittest tests/test_scraper.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add scraper (Stages 1-3) with tests"
```

---

### Task 7: Downloader

**Files:**
- Create: `downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_downloader.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m unittest tests/test_downloader.py -v
```
Expected: FAIL — ModuleNotFoundError: No module named 'downloader'

- [ ] **Step 3: Write downloader.py**

```python
"""Downloader: Stage 4 — ZIP download, extract, rename."""
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse
import requests
from config import (
    DOWNLOAD_DIR, DOWNLOAD_URL, DOWNLOAD_TIMEOUT, CHUNK_SIZE,
    KEEP_ZIP, MIN_VALID_FILE_SIZE, REQUEST_TIMEOUT, USE_PROXY,
)
from utils.headers import get_download_headers, get_browser_headers
from utils.sanitize import clean_filename, clean_foldername, extract_timestamp_from_zip, generate_doc_filename
from utils.helpers import sleep_jitter


class Downloader:
    def __init__(self, storage, log, use_proxy: bool = USE_PROXY, proxy_manager=None):
        self.storage = storage
        self.log = log
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.session.headers.update(get_browser_headers())
        if use_proxy and proxy_manager:
            self.session.proxies.update(proxy_manager.get_local_proxy())
        self._consecutive_failures = 0

    def close(self):
        self.session.close()

    def get_download_page_url(self, post_id: str) -> str:
        return DOWNLOAD_URL.format(post_id)

    def get_category_dir(self, category_id: str, category_name: str) -> Path:
        folder = f"{category_id}_{clean_foldername(category_name)}"
        path = DOWNLOAD_DIR / folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generate_filename(self, zip_filename: str, report_title: str) -> str:
        return generate_doc_filename(zip_filename, report_title)

    def _download_zip(self, zip_url: str, referer: str, save_path: Path) -> Tuple[bool, int]:
        try:
            headers = get_download_headers(referer)
            resp = self.session.get(zip_url, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT)
            if resp.status_code == 403:
                self.log.error(f"403 Forbidden: {zip_url}")
                return False, 0
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type.lower() and zip_url.endswith(".zip"):
                self.log.error("Received HTML instead of ZIP")
                return False, 0
            total = int(resp.headers.get("Content-Length", 0))
            save_path.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
            return True, size
        except Exception as e:
            self.log.error(f"Download failed: {e}")
            return False, 0

    def _extract_zip(self, zip_path: Path, extract_dir: Path, report_title: str) -> bool:
        try:
            if not zipfile.is_zipfile(zip_path):
                self.log.error(f"Invalid ZIP: {zip_path}")
                return False
            timestamp = extract_timestamp_from_zip(zip_path.name)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    clean = clean_filename(name)
                    target = extract_dir / clean
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    if target.suffix.lower() in {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}:
                        new_name = generate_doc_filename(zip_path.name, report_title)
                        new_path = extract_dir / clean_filename(new_name)
                        if new_path != target:
                            target.rename(new_path)
                            self.log.ok(f"  Renamed: {clean} → {new_path.name}")
            return True
        except Exception as e:
            self.log.error(f"Extraction failed: {e}")
            return False

    def _switch_proxy_and_retry(self) -> bool:
        if self.proxy_manager:
            self.log.warn("Switching proxy node...")
            if self.proxy_manager.switch_node():
                self.session.proxies.update(self.proxy_manager.get_local_proxy())
                self.session.cookies.clear()
                sleep_jitter(1, 2)
                return True
        return False

    def download_report(self, report: dict, keep_zip: bool = KEEP_ZIP) -> bool:
        post_id = report["post_id"]
        title = report.get("title", "unknown")
        zip_url = report.get("download_url", "")
        category_id = report.get("category_id", "0")
        category_name = report.get("category_name", "unknown")
        publish_date = report.get("publish_date", "")

        if not zip_url:
            self.log.warn(f"No download URL for {post_id}")
            return False

        download_page_url = self.get_download_page_url(post_id)
        cat_dir = self.get_category_dir(category_id, category_name)
        zip_filename = os.path.basename(urlparse(zip_url).path)
        zip_path = cat_dir / clean_filename(zip_filename)

        # Check if already downloaded
        doc_pattern = f"{extract_timestamp_from_zip(zip_filename)}_{clean_filename(title)}"
        existing = list(cat_dir.glob(f"{doc_pattern[:20]}*"))
        if existing:
            for f in existing:
                if f.stat().st_size > MIN_VALID_FILE_SIZE:
                    self.log.info(f"Already downloaded: {f.name}")
                    return True

        self.log.info(f"Downloading: {title[:40]}")

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                self.log.info(f"  Attempt {attempt}/{max_attempts}")
            # Visit download page first
            try:
                self.session.get(download_page_url, headers=get_browser_headers(), timeout=REQUEST_TIMEOUT)
                sleep_jitter(0.5, 1.0)
            except Exception as e:
                self.log.warn(f"Failed to visit download page: {e}")

            ok, size = self._download_zip(zip_url, download_page_url, zip_path)
            if not ok:
                self._consecutive_failures += 1
                if attempt < max_attempts:
                    if self._consecutive_failures >= 2 or self._switch_proxy_and_retry():
                        continue
                self.log.error(f"Download failed: {post_id}")
                self.storage.append("reports", {
                    "type": "download_failed",
                    "post_id": post_id,
                    "error": f"attempt {attempt}",
                })
                return False

            if size < MIN_VALID_FILE_SIZE:
                self.log.error(f"Downloaded file too small: {size} bytes")
                if zip_path.exists():
                    zip_path.unlink()
                continue

            self.log.ok(f"Downloaded: {zip_filename} ({size / 1024:.1f} KB)")

            # Extract
            if self._extract_zip(zip_path, cat_dir, title):
                self.log.ok(f"Extracted: {title[:40]}")
                if not keep_zip and zip_path.exists():
                    zip_path.unlink()
            else:
                self.log.warn(f"Extraction failed, keeping ZIP: {zip_path.name}")

            self.storage.append("reports", {
                "type": "download_completed",
                "post_id": post_id,
                "file_path": str(cat_dir),
                "file_size": size,
            })
            self._consecutive_failures = 0
            return True

        self.log.error(f"All attempts failed for {post_id}")
        return False

    def download_all_ready(self, max_reports: int = None, keep_zip: bool = KEEP_ZIP) -> dict:
        self.log.info("Stage 4: Downloading all ready reports")
        ready = self.storage.query_by_status("reports", "ready")
        if max_reports:
            ready = ready[:max_reports]
        self.log.info(f"  Ready reports: {len(ready)}")
        stats = {"success": 0, "failed": 0}
        for i, report in enumerate(ready):
            self.log.info(f"  [{i+1}/{len(ready)}]")
            if self.download_report(report, keep_zip=keep_zip):
                stats["success"] += 1
            else:
                stats["failed"] += 1
            if i < len(ready) - 1:
                sleep_jitter(1.5, 2.5)
        self.log.info(f"  Stage 4 complete: {stats['success']} success, {stats['failed']} failed")
        return stats

    def extract_downloaded_zips(self, max_reports: int = None, keep_zip: bool = True):
        self.log.info("Extracting downloaded ZIPs")
        # Find ZIP files in download directory
        zips = list(DOWNLOAD_DIR.rglob("*.zip"))
        if max_reports:
            zips = zips[:max_reports]
        for zip_path in zips:
            # Extract category from path
            parts = zip_path.relative_to(DOWNLOAD_DIR).parts
            category_part = parts[0] if parts else "unknown"
            cat_id, *cat_name = category_part.split("_", 1)
            cat_name = cat_name[0] if cat_name else category_part
            if self._extract_zip(zip_path, zip_path.parent, cat_name):
                self.log.ok(f"Extracted: {zip_path.name}")
                if not keep_zip:
                    zip_path.unlink()
            else:
                self.log.error(f"Failed to extract: {zip_path.name}")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m unittest tests/test_downloader.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add downloader.py tests/test_downloader.py
git commit -m "feat: add downloader (Stage 4) with tests"
```

---

### Task 8: Main CLI

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
"""CLI entry point for ipoipo downloader."""
import sys
import argparse
from config import USE_PROXY, PROXY_CONFIG_PATH
from logger import get_logger, Logger
from storage import Storage
from proxy import ProxyManager
from scraper import Scraper
from downloader import Downloader
from config import LOG_DIR, DATA_DIR


def main():
    parser = argparse.ArgumentParser(description="ipoipo.cn report downloader")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--stage1", action="store_true", help="Stage 1: categories")
    parser.add_argument("--stage2", action="store_true", help="Stage 2: report lists")
    parser.add_argument("--stage3", action="store_true", help="Stage 3: download URLs")
    parser.add_argument("--stage4", action="store_true", help="Stage 4: download reports")
    parser.add_argument("--retry", action="store_true", help="Retry failed downloads")
    parser.add_argument("--extract", action="store_true", help="Extract ZIPs only")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--max-pages", type=int, help="Max pages per category")
    parser.add_argument("--max-reports", type=int, help="Max reports to process")
    parser.add_argument("--limit", type=int, help="Limit for stage 3")
    parser.add_argument("--category", type=str, help="Category ID")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy")
    parser.add_argument("--keep-zip", action="store_true", help="Keep ZIP after extraction")
    args = parser.parse_args()

    if not any([args.full, args.stage1, args.stage2, args.stage3, args.stage4, args.retry, args.extract, args.stats]):
        parser.print_help()
        sys.exit(0)

    use_proxy = not args.no_proxy and USE_PROXY
    log = get_logger("main", jsonl_path=str(LOG_DIR / "events.jsonl"))
    storage = Storage(str(DATA_DIR))

    proxy_manager = None
    if use_proxy:
        try:
            proxy_manager = ProxyManager(str(PROXY_CONFIG_PATH))
            proxy_manager.test_all_nodes()
            proxy_manager.select_random()
            log.ok(f"Proxy: {proxy_manager.current_node.name}")
        except Exception as e:
            log.error(f"Proxy init failed: {e}, continuing without proxy")
            use_proxy = False

    scraper = Scraper(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)
    dl = Downloader(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)

    try:
        if args.stats:
            stats = storage.get_stats()
            log.info(f"Categories: {stats['total_categories']}")
            log.info(f"Reports: {stats['total_reports']}")
            log.info(f"By status: {stats['by_status']}")

        if args.stage1:
            scraper.scrape_all_categories()

        if args.stage2:
            scraper.scrape_all_categories(max_pages=args.max_pages)

        if args.stage3:
            scraper.process_pending_reports(limit=args.limit)

        if args.stage4:
            dl.download_all_ready(max_reports=args.max_reports, keep_zip=args.keep_zip)

        if args.retry:
            from storage import STATUS_MAP
            # Reset failed to ready by appending url_found events
            failed = storage.query_by_status("reports", "failed")
            if args.max_reports:
                failed = failed[:args.max_reports]
            log.info(f"Retrying {len(failed)} failed reports")
            for r in failed:
                storage.append("reports", {
                    "type": "url_found",
                    "post_id": r["post_id"],
                    "download_url": r.get("download_url", ""),
                })
            dl.download_all_ready(max_reports=len(failed), keep_zip=args.keep_zip)

        if args.extract:
            dl.extract_downloaded_zips(max_reports=args.max_reports, keep_zip=args.keep_zip)

        if args.full:
            scraper.scrape_all_categories()
            scraper.scrape_all_categories(max_pages=args.max_pages)
            scraper.process_pending_reports(limit=args.limit)
            dl.download_all_ready(max_reports=args.max_reports, keep_zip=args.keep_zip)

        if not args.stats:
            stats = storage.get_stats()
            log.info(f"Final stats: {stats}")

    except KeyboardInterrupt:
        log.warn("Interrupted by user")
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        scraper.close()
        dl.close()
        storage.close()
        log.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test CLI help**

```bash
python main.py --help
```
Expected: Shows all arguments

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add CLI entry point with all pipeline commands"
```

---

### Task 9: Scripts + README

**Files:**
- Create: `scripts/run.sh`
- Create: `scripts/run_stage.sh`
- Create: `scripts/stats.sh`
- Create: `README.md`

- [ ] **Step 1: Create scripts/run.sh**

```bash
#!/bin/bash
# Run full pipeline in background
nohup python main.py --full > logs/output.log 2>&1 &
echo "Started in background (PID: $!)"
echo "Logs: logs/output.log"
```

- [ ] **Step 2: Create scripts/run_stage.sh**

```bash
#!/bin/bash
# Run a single stage
# Usage: bash run_stage.sh <stage_number> [additional args]
STAGE=$1
shift
case $STAGE in
    1) python main.py --stage1 "$@" ;;
    2) python main.py --stage2 "$@" ;;
    3) python main.py --stage3 "$@" ;;
    4) python main.py --stage4 "$@" ;;
    *) echo "Usage: $0 <1|2|3|4> [args]"; exit 1 ;;
esac
```

- [ ] **Step 3: Create scripts/stats.sh**

```bash
#!/bin/bash
# Quick stats from JSONL files
echo "=== ipoipo Downloader Stats ==="
echo ""
echo "Categories: $(wc -l < data/categories.jsonl 2>/dev/null || echo 0)"
echo "Reports (events): $(wc -l < data/reports.jsonl 2>/dev/null || echo 0)"
echo "Downloads (events): $(wc -l < data/downloads.jsonl 2>/dev/null || echo 0)"
echo ""
echo "Reports by status:"
python -c "
from storage import Storage
s = Storage('data')
stats = s.get_stats()
for status, count in sorted(stats['by_status'].items()):
    print(f'  {status}: {count}')
s.close()
"
echo ""
echo "Downloaded files: $(find data/downloads -type f ! -name '*.zip' 2>/dev/null | wc -l)"
```

- [ ] **Step 4: Create README.md**

```markdown
# ipoipo Downloader

IPO industry report scraper for ipoipo.cn. Downloads reports as PDF/Word/Excel files.

## Quick Start

```bash
pip install -r requirements.txt
python main.py --full --max-pages 2 --max-reports 10
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py --full` | Run all stages |
| `python main.py --stage1` | Scrape categories |
| `python main.py --stage2 --max-pages 5` | Scrape report lists |
| `python main.py --stage3 --limit 50` | Get download URLs |
| `python main.py --stage4 --max-reports 20` | Download reports |
| `python main.py --retry --max-reports 10` | Retry failed downloads |
| `python main.py --extract` | Extract ZIPs only |
| `python main.py --stats` | Show statistics |
| `python main.py --full --no-proxy` | Run without proxy |
| `python main.py --keep-zip` | Keep ZIP files after extraction |

## Architecture

Event-driven pipeline with JSONL storage:

```
main.py → Scraper (Stages 1-3) → Downloader (Stage 4)
                ↓                       ↓
          storage.py (JSONL)      storage.py (JSONL)
```

### Modules

| File | Responsibility |
|------|---------------|
| `config.py` | URLs, categories, settings |
| `scraper.py` | HTML scraping, event emission |
| `downloader.py` | ZIP download, extraction, rename |
| `storage.py` | JSONL append/query, state derivation |
| `logger.py` | Dual output (console + JSONL) |
| `proxy.py` | Clash config, node selection, auto-switch |
| `utils/` | Headers, filename sanitization, helpers |

## Proxy

Requires Clash running locally. Config in `config/proxy.yaml`.

## Anti-Hotlinking

ZIP files on `ipo.ai-tag.cn` require Referer from `ipoipo.cn`. The scraper visits the download page first, then downloads with correct Referer.

## File Organization

```
data/downloads/
├── 85_人工智能AI行业/
│   ├── 20251222_报告标题.pdf
│   └── ...
└── 7_教育行业/
    └── ...
```

## Logs

- Console: colored real-time output
- File: `logs/events.jsonl` (structured JSON for analysis)
```

- [ ] **Step 5: Make scripts executable**

```bash
chmod +x scripts/*.sh
```

- [ ] **Step 6: Commit**

```bash
git add scripts/ README.md
git commit -m "feat: add shell scripts and README"
```

---

### Task 10: Run All Tests

- [ ] **Step 1: Run full test suite**

```bash
python -m unittest discover tests/ -v
```
Expected: All tests pass

- [ ] **Step 2: Commit**

```bash
git commit --allow-empty -m "chore: all tests passing"
```

---

## Self-Review

**1. Spec coverage check:**
- ✅ JSONL storage with categories.jsonl, reports.jsonl, downloads.jsonl
- ✅ Dual-output logging (console + JSON file)
- ✅ Domain-driven modules (scraper, downloader, storage, logger, proxy, config, utils)
- ✅ Sequential execution with auto proxy-switch
- ✅ Flat file organization by category with clean naming
- ✅ CLI commands matching spec
- ✅ Shell scripts (run.sh, run_stage.sh, stats.sh)
- ✅ .gitignore, README.md, requirements.txt
- ✅ Anti-hotlinking bypass with Referer
- ✅ Error handling table implemented
- ✅ Event-driven pipeline with status derivation

**2. Placeholder scan:** No TBD/TODO patterns found. All code steps contain complete implementations.

**3. Type consistency:** All modules use consistent interfaces: `storage.append()`, `storage.query_by_status()`, `storage.get_state()`, `log.info/ok/warn/error()`.

**4. No "similar to Task N" patterns:** Each task contains complete, self-contained code.
