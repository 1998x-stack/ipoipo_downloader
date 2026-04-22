"""Scraper: Stage 1-3 — categories, report lists, download URLs.

Implements the first three stages of the ipoipo downloader pipeline:

- **Stage 1 (Category Discovery):** Scrapes the category index page to discover
  all 38 report categories (TMT, AI, Finance, etc.) and stores them in
  ``categories.jsonl``.

- **Stage 2 (Report Listing):** Paginates through each category's report listing,
  extracting post IDs, titles, thumbnails, view counts, and publish dates.
  Emits ``report_found`` events to ``reports.jsonl``.

- **Stage 3 (Download URL Extraction):** Visits each report's download page,
  extracts the ZIP file URL from the HTML using a 4-method fallback chain.
  Emits ``url_found`` events to ``reports.jsonl``.

Key design decisions:
- HTML parsing uses BeautifulSoup with lxml for speed and robustness.
- Pagination follows the website's ``tags-{id}_{page}.html`` URL pattern.
- Proxy error recovery uses exponential backoff (failures * 5s, max 30s)
  with automatic node switching after 5 consecutive failures.
- ZIP URL extraction employs 4 fallback methods: href suffix, style pattern,
  link text, and raw regex — ordered from most reliable to least.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag
import requests

from config import (
    CATEGORY_NAMES,
    CATEGORY_PAGE_PAGINATED,
    CATEGORY_PAGE_URL,
    DOWNLOAD_URL,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USE_PROXY,
)
from utils.headers import get_browser_headers
from utils.helpers import sleep_jitter


class Scraper:
    """HTTP scraper for ipoipo.cn, implementing stages 1-3 of the pipeline.

    This class manages an HTTP session with browser-like headers and optional
    proxy support. It discovers categories, paginates through report listings,
    and extracts download URLs from HTML pages.

    The scraper integrates with:
    - ``Storage`` for append-only JSONL event logging and checkpoint tracking.
    - ``Logger`` for dual-output (console + JSONL file) logging.
    - ``ProxyManager`` for dynamic proxy node switching on failure.

    Attributes:
        storage: Storage backend for JSONL event logging and progress tracking.
            Must implement ``append()``, ``_read_lines()``, ``save_progress()``,
            ``get_progress()``, and ``get_category_report_count()``.
        log: Logger instance for console and file output.
            Must implement ``info()``, ``ok()```, ``warn()``, and ``error()``.
        use_proxy: Whether to route requests through a proxy.
        proxy_manager: Optional proxy manager for dynamic node switching.
        session: requests.Session with browser headers and proxy configuration.
    """

    def __init__(
        self,
        storage: Any,
        log: Any,
        use_proxy: bool = USE_PROXY,
        proxy_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the Scraper with storage, logging, and proxy settings.

        Creates a persistent HTTP session with browser-like headers. If proxy
        is enabled and a proxy manager is provided, configures the session
        to route through the local proxy.

        Args:
            storage: Storage backend for JSONL event logging.
            log: Logger instance for console and file output.
            use_proxy: Whether to enable proxy routing. Defaults to the value
                from ``config.USE_PROXY``.
            proxy_manager: Optional ProxyManager for dynamic node switching
                on consecutive failures.
        """
        self.storage: Any = storage
        self.log: Any = log
        self.use_proxy: bool = use_proxy
        self.proxy_manager: Optional[Any] = proxy_manager
        self.session: requests.Session = requests.Session()
        self.session.headers.update(get_browser_headers())
        if use_proxy and proxy_manager:
            self.session.proxies.update(proxy_manager.get_local_proxy())

    def close(self) -> None:
        """Close the underlying HTTP session and release connections."""
        self.session.close()

    # ── Stage 1: Categories ──

    def scrape_categories(self, resume: bool = False) -> List[Dict[str, Any]]:
        """Stage 1: Discover all categories and store them in JSONL.

        Iterates over the predefined ``CATEGORY_NAMES`` mapping from config,
        emitting a ``category`` event for each entry. When ``resume=True``,
        reads existing entries from ``categories.jsonl`` and skips already-
        discovered categories.

        Args:
            resume: If True, read existing categories from storage and skip
                those already discovered. Defaults to False.

        Returns:
            List of category dicts, each containing ``category_id``,
            ``category_name``, and ``url`` keys.
        """
        self.log.info("Stage 1: Scraping categories")
        existing_ids: set[str] = set()
        if resume:
            category_lines: List[str] = self.storage._read_lines("categories")
            existing_ids = {
                json.loads(line)["category_id"]
                for line in category_lines
                if line.strip()
            }
            self.log.info(f"  Found {len(existing_ids)} existing categories, skipping")

        categories: List[Dict[str, Any]] = []
        for category_id, category_name in CATEGORY_NAMES.items():
            if resume and category_id in existing_ids:
                continue
            url: str = CATEGORY_PAGE_URL.format(category_id)
            self.storage.append(
                "categories",
                {
                    "type": "category",
                    "category_id": category_id,
                    "category_name": category_name,
                    "url": url,
                },
            )
            self.log.ok(f"category:{category_id} {category_name}")
            categories.append(
                {
                    "category_id": category_id,
                    "category_name": category_name,
                    "url": url,
                }
            )
        self.log.info(f"Total categories: {len(categories)}")
        return categories

    # ── Stage 2: Report Lists ──

    def scrape_page(self, url: str) -> List[Dict[str, Any]]:
        """Fetch and parse a single page, returning extracted report metadata.

        Sends an HTTP GET request to the given URL, parses the HTML response
        with BeautifulSoup, and extracts all report cards matching the
        ``div.wapost.card`` selector. Each card is parsed via
        ``parse_report_card()``.

        Handles proxy errors, connection errors, and generic exceptions
        gracefully by returning an empty list and logging the error.

        Args:
            url: The full URL of the page to scrape.

        Returns:
            List of report dicts extracted from the page. Returns an empty
            list on any error (proxy, connection, or parsing failure).
        """
        try:
            resp: requests.Response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup: BeautifulSoup = BeautifulSoup(resp.text, "lxml")
            cards: List[Tag] = soup.find_all("div", class_="wapost card")
            reports: List[Dict[str, Any]] = []
            for card in cards:
                report: Optional[Dict[str, Any]] = self.parse_report_card(card)
                if report:
                    reports.append(report)
            return reports
        except requests.exceptions.ProxyError as exc:
            self.log.error(f"Proxy error on {url}: {exc}")
            return []
        except requests.exceptions.ConnectionError as exc:
            error_str: str = str(exc).lower()
            if "refused" in error_str or "proxy" in error_str:
                self.log.error(f"Connection refused (proxy down?) on {url}: {exc}")
            else:
                self.log.error(f"Connection error on {url}: {exc}")
            return []
        except Exception as exc:
            self.log.error(f"Failed to scrape page: {url} — {exc}")
            return []

    def parse_report_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Extract report metadata from a single HTML card element.

        Parses the card's DOM structure to extract:
        - ``post_id`` from the ``/post/{id}.html`` URL pattern in the title link.
        - ``title`` from the ``<a>`` element's ``title`` attribute.
        - ``detail_url`` from the ``<a>`` element's ``href`` attribute.
        - ``thumbnail_url`` from the ``<img>`` element's ``src`` attribute.
        - ``description`` from the ``<p class="text">`` element's text content.
        - ``view_count`` from the ``<span class="view-num">`` element's digits.
        - ``publish_date`` from the ``<span class="edit">`` element's text.

        Args:
            card: A BeautifulSoup Tag representing a ``div.wapost.card`` element.

        Returns:
            Dict with report metadata keys, or None if the card is missing
            required elements (title link or post ID).
        """
        try:
            title_heading: Optional[Tag] = card.find("h2", class_="multi-ellipsis")
            if not title_heading:
                return None
            title_link: Optional[Tag] = title_heading.find("a")
            if not title_link:
                return None
            title: str = title_link.get("title", "").strip()
            detail_url: str = title_link.get("href", "").strip()
            regex_match: Optional[re.Match[str]] = re.search(
                r"/post/(\d+)\.html", detail_url
            )
            if not regex_match:
                return None
            post_id: str = regex_match.group(1)

            thumbnail_img: Optional[Tag] = card.find("img", class_="img-cover")
            thumbnail_url: str = thumbnail_img.get("src", "") if thumbnail_img else ""

            description_paragraph: Optional[Tag] = card.find("p", class_="text")
            description: str = (
                description_paragraph.get_text(strip=True)
                if description_paragraph
                else ""
            )

            count_div: Optional[Tag] = card.find("div", class_="count")
            view_count: int = 0
            publish_date: str = ""
            if count_div:
                view_span: Optional[Tag] = count_div.find("span", class_="view-num")
                if view_span:
                    digits_match: Optional[re.Match[str]] = re.search(
                        r"\d+", view_span.get_text(strip=True)
                    )
                    if digits_match:
                        view_count = int(digits_match.group())
                edit_span: Optional[Tag] = count_div.find("span", class_="edit")
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
        except Exception as exc:
            self.log.error(f"Failed to parse report card: {exc}")
            return None

    def scrape_category(
        self,
        category_id: str,
        category_name: str,
        max_pages: Optional[int] = None,
        start_page: int = 1,
    ) -> List[Dict[str, Any]]:
        """Stage 2: Scrape all report listings for a single category.

        Paginates through the category's report pages starting from
        ``start_page``. For each page, extracts report cards and emits
        ``report_found`` events to storage. Saves per-page checkpoints
        via ``storage.save_progress()`` for resume support.

        Proxy error recovery strategy:
        - On proxy/connection error, increment failure counter.
        - Wait ``min(proxy_failures * 5, 30)`` seconds before retry.
        - After 5 consecutive failures, attempt proxy node switch.
        - If switch succeeds, reset failure counter and continue.
        - If switch fails or no manager available, stop scraping this category.

        Args:
            category_id: The category ID (e.g., "85").
            category_name: The category name in Chinese (e.g., "人工智能AI行业").
            max_pages: Maximum number of pages to scrape. None for unlimited.
            start_page: The page number to start from (1-based). Defaults to 1.

        Returns:
            List of all report dicts discovered across all scraped pages.
        """
        self.log.info(
            f"Stage 2: Scraping category:{category_id} {category_name} "
            f"(from page {start_page})"
        )
        all_reports: List[Dict[str, Any]] = []
        page: int = start_page
        proxy_failures: int = 0
        max_proxy_retries: int = 5

        while True:
            # 构造当前页 URL：第 1 页与后续分页使用不同的 URL 模板
            url: str = (
                CATEGORY_PAGE_URL.format(category_id)
                if page == 1
                else CATEGORY_PAGE_PAGINATED.format(category_id, page)
            )
            self.log.info(f"  Page {page}: {url}")

            try:
                reports: List[Dict[str, Any]] = self.scrape_page(url)
                proxy_failures = 0
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
                proxy_failures += 1
                if proxy_failures >= max_proxy_retries:
                    # 连续失败达到上限，尝试切换代理节点
                    if self.proxy_manager:
                        self.log.warn(
                            f"Proxy failed {proxy_failures} times, switching node..."
                        )
                        if self.proxy_manager.switch_node():
                            self.session.proxies.update(
                                self.proxy_manager.get_local_proxy()
                            )
                            self.session.cookies.clear()
                            proxy_failures = 0
                            time.sleep(5)
                            continue
                    self.log.error(
                        f"Proxy failed {proxy_failures} times with no recovery, "
                        f"stopping category {category_id}"
                    )
                    break
                # 指数退避等待：每次失败等待时间递增，上限 30 秒
                wait: int = min(proxy_failures * 5, 30)
                self.log.warn(
                    f"Proxy error (attempt {proxy_failures}/{max_proxy_retries}), "
                    f"waiting {wait}s before retry..."
                )
                time.sleep(wait)
                continue

            if not reports:
                self.log.info(f"  Page {page} has no data, stopping")
                break

            new_count: int = 0
            for report in reports:
                self.storage.append(
                    "reports",
                    {
                        "type": "report_found",
                        "post_id": report["post_id"],
                        "category_id": category_id,
                        "category_name": category_name,
                        "title": report["title"],
                        "detail_url": report["detail_url"],
                        "thumbnail_url": report["thumbnail_url"],
                        "view_count": report["view_count"],
                        "publish_date": report["publish_date"],
                    },
                )
                new_count += 1
                self.log.ok(f"  report:{report['post_id']} {report['title'][:40]}")

            all_reports.extend(reports)
            self.storage.save_progress(category_id, page)

            if max_pages is not None and page >= max_pages:
                break
            page += 1
            sleep_jitter(*REQUEST_DELAY)

        self.log.info(
            f"  Total reports for {category_name}: {len(all_reports)} ({new_count} new)"
        )
        self.storage.save_progress(category_id, 0)
        return all_reports

    def scrape_all_categories(
        self, max_pages: Optional[int] = None, resume: bool = False
    ) -> None:
        """Stage 2: Scrape report lists for all discovered categories.

        Reads categories from ``categories.jsonl`` (discovering them first
        if the file doesn't exist). Iterates through each category and calls
        ``scrape_category()``.

        When ``resume=True``:
        - Checks ``progress.json`` for the last completed page.
        - If progress exists, resumes from the next page.
        - If the category already has reports, skips it entirely.

        Args:
            max_pages: Maximum pages per category. None for unlimited.
            resume: If True, resume from last checkpoint and skip completed
                categories. Defaults to False.
        """
        category_lines: List[str] = self.storage._read_lines("categories")
        if not category_lines:
            self.scrape_categories()
            category_lines = self.storage._read_lines("categories")

        total_categories: int = len(category_lines)
        for index, line in enumerate(category_lines, 1):
            category: Dict[str, Any] = json.loads(line)
            category_id: str = category["category_id"]
            category_name: str = category["category_name"]

            if resume:
                last_page: int = self.storage.get_progress(category_id)
                if last_page > 0:
                    self.log.info(
                        f"[{index}/{total_categories}] Resuming "
                        f"category:{category_id} {category_name} "
                        f"from page {last_page + 1}"
                    )
                    self.scrape_category(
                        category_id,
                        category_name,
                        max_pages=max_pages,
                        start_page=last_page + 1,
                    )
                    continue

                existing_count: int = self.storage.get_category_report_count(
                    category_id
                )
                if existing_count > 0:
                    self.log.info(
                        f"[{index}/{total_categories}] Skipping "
                        f"category:{category_id} {category_name} "
                        f"({existing_count} reports already)"
                    )
                    continue

            self.log.info(
                f"[{index}/{total_categories}] Processing "
                f"category:{category_id} {category_name}"
            )
            self.scrape_category(category_id, category_name, max_pages=max_pages)

    # ── Stage 3: Download URLs ──

    def get_download_page_url(self, post_id: str) -> str:
        """Build the download page URL for a given post ID.

        Args:
            post_id: The numeric post ID (e.g., "26028").

        Returns:
            The full download page URL (e.g.,
            ``https://ipoipo.cn/download/26028.html``).
        """
        return DOWNLOAD_URL.format(post_id)

    def extract_zip_url(
        self, html: str, base_url: Optional[str] = None
    ) -> Optional[str]:
        """Extract the ZIP download URL from an HTML page using 4 fallback methods.

        The extraction chain tries methods in order of reliability:

        1. **href suffix match:** Finds ``<a>`` elements whose ``href`` attribute
           ends with ``.zip`` (case-insensitive). Most reliable method.

        2. **Style pattern match:** Finds ``<a>`` elements with inline styles
           containing both ``font-size`` and ``color``. Some download links
           are styled this way. Checks if ``.zip`` appears in href or text.

        3. **Text content match:** Finds ``<a>`` elements whose visible text
           contains ``.zip``. Catches links with descriptive text like
           "Download ZIP".

        4. **Raw regex match:** Searches the raw HTML string for URLs matching
           ``http(s)://...zip``. Catches URLs embedded in JavaScript or
           non-standard HTML.

        Args:
            html: The HTML content to parse. Can be empty string.
            base_url: Optional base URL for resolving relative links.
                When provided, relative hrefs are joined with this URL
                via ``urllib.parse.urljoin``.

        Returns:
            The first matching ZIP URL found, or None if no ZIP link exists.
        """
        from urllib.parse import urljoin

        soup: BeautifulSoup = BeautifulSoup(html, "lxml")

        # Method 1: href ends with .zip — 最可靠的方法，直接匹配链接后缀
        zip_links: List[Tag] = soup.find_all("a", href=re.compile(r"\.zip$", re.I))
        if zip_links:
            first_link: Tag = zip_links[0]
            href: str = first_link.get("href", "")
            return urljoin(base_url, href) if base_url else href

        # Method 2: style with font-size + color — 匹配带内联样式的下载链接
        styled_links: List[Tag] = soup.find_all(
            "a", style=re.compile(r"font-size.*color")
        )
        for link in styled_links:
            link_href: str = link.get("href", "")
            link_text: str = link.get_text(strip=True)
            if ".zip" in link_href.lower() or ".zip" in link_text.lower():
                return urljoin(base_url, link_href) if base_url else link_href

        # Method 3: text contains .zip — 匹配链接文本包含 .zip 的元素
        for link in soup.find_all("a"):
            text: str = link.get_text(strip=True)
            if ".zip" in text.lower():
                text_href: str = link.get("href", "")
                if text_href:
                    return urljoin(base_url, text_href) if base_url else text_href

        # Method 4: regex on raw HTML — 兜底方案，直接正则匹配原始 HTML 中的 URL
        url_matches: List[str] = re.findall(
            r'https?://[^\s<>"'']+.zip', html, re.I
        )
        if url_matches:
            return url_matches[0]

        return None

    def visit_download_page(
        self, post_id: str
    ) -> Tuple[bool, Optional[str], str]:
        """Fetch the download page HTML for a given post ID.

        Sends an HTTP GET request to the download page URL. The response
        HTML is needed for ``extract_zip_url()`` to find the actual ZIP
        file URL.

        Args:
            post_id: The numeric post ID (e.g., "26028").

        Returns:
            A tuple of (success, html_content, page_url):
            - success: True if the request succeeded (HTTP 2xx).
            - html_content: The response HTML text, or None on failure.
            - page_url: The download page URL (always returned).
        """
        url: str = self.get_download_page_url(post_id)
        try:
            resp: requests.Response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return True, resp.text, url
        except Exception as exc:
            self.log.error(f"Failed to visit download page for {post_id}: {exc}")
            return False, None, url

    def process_pending_reports(self, limit: int = 100) -> None:
        """Stage 3: Extract download URLs for pending reports.

        Queries storage for reports with ``pending`` status (last event type
        is ``report_found``). For each pending report:
        1. Visits the download page to establish session cookies.
        2. Waits 0.5-1s to simulate human behavior.
        3. Extracts the ZIP URL from the HTML using ``extract_zip_url()``.
        4. Emits a ``url_found`` event if a ZIP URL is found.
        5. Waits 1.5-2.5s between reports to avoid rate limiting.

        Args:
            limit: Maximum number of pending reports to process.
                None for unlimited. Defaults to 100.
        """
        self.log.info("Stage 3: Processing pending reports for download URLs")
        pending: List[Dict[str, Any]] = self.storage.query_by_status(
            "reports", "pending"
        )
        if limit is not None:
            pending = pending[:limit]
        self.log.info(f"  Pending reports: {len(pending)}")

        success_count: int = 0
        fail_count: int = 0
        total_pending: int = len(pending)

        for index, report in enumerate(pending):
            post_id: str = report["post_id"]
            title: str = report.get("title", "")
            self.log.info(f"  [{index + 1}/{total_pending}] {title[:40]}")

            ok: bool
            html: Optional[str]
            page_url: str
            ok, html, page_url = self.visit_download_page(post_id)
            if not ok or not html:
                fail_count += 1
                continue

            sleep_jitter(0.5, 1.0)
            zip_url: Optional[str] = self.extract_zip_url(html, base_url=page_url)
            if zip_url:
                self.storage.append(
                    "reports",
                    {
                        "type": "url_found",
                        "post_id": post_id,
                        "download_url": zip_url,
                    },
                )
                self.log.ok(f"  URL found: {post_id}")
                success_count += 1
            else:
                self.log.warn(f"  No ZIP URL for {post_id}")
                fail_count += 1

            if index < total_pending - 1:
                sleep_jitter(1.5, 2.5)

        self.log.info(
            f"  Stage 3 complete: {success_count} success, {fail_count} failed"
        )
