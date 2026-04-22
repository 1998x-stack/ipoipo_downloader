"""Scraper: Stage 1-3 — categories, report lists, download URLs."""
import json
import re
import time
from typing import List, Dict, Optional, Tuple
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

    def scrape_categories(self, resume: bool = False) -> List[Dict]:
        """Stage 1: Scrape all categories and store them."""
        self.log.info("Stage 1: Scraping categories")
        existing_ids = set()
        if resume:
            cat_lines = self.storage._read_lines("categories")
            existing_ids = {json.loads(l)["category_id"] for l in cat_lines if l.strip()}
            self.log.info(f"  Found {len(existing_ids)} existing categories, skipping")
        categories = []
        for cat_id, cat_name in CATEGORY_NAMES.items():
            if resume and cat_id in existing_ids:
                continue
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
        except requests.exceptions.ProxyError as e:
            self.log.error(f"Proxy error on {url}: {e}")
            raise  # Re-raise proxy errors so caller can handle them
        except requests.exceptions.ConnectionError as e:
            if "refused" in str(e).lower() or "proxy" in str(e).lower():
                self.log.error(f"Connection refused (proxy down?) on {url}: {e}")
                raise
            self.log.error(f"Connection error on {url}: {e}")
            return []
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

    def scrape_category(self, category_id: str, category_name: str, max_pages: int = None, start_page: int = 1) -> List[Dict]:
        self.log.info(f"Stage 2: Scraping category:{category_id} {category_name} (from page {start_page})")
        all_reports = []
        page = start_page
        proxy_failures = 0
        max_proxy_retries = 5
        while True:
            url = CATEGORY_PAGE_URL.format(category_id) if page == 1 else CATEGORY_PAGE_PAGINATED.format(category_id, page)
            self.log.info(f"  Page {page}: {url}")
            try:
                reports = self.scrape_page(url)
                proxy_failures = 0
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                proxy_failures += 1
                if proxy_failures >= max_proxy_retries:
                    if self.proxy_manager:
                        self.log.warn(f"Proxy failed {proxy_failures} times, switching node...")
                        if self.proxy_manager.switch_node():
                            self.session.proxies.update(self.proxy_manager.get_local_proxy())
                            self.session.cookies.clear()
                            proxy_failures = 0
                            time.sleep(5)
                            continue
                    self.log.error(f"Proxy failed {proxy_failures} times with no recovery, stopping category {category_id}")
                    break
                wait = min(proxy_failures * 5, 30)
                self.log.warn(f"Proxy error (attempt {proxy_failures}/{max_proxy_retries}), waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            if not reports:
                self.log.info(f"  Page {page} has no data, stopping")
                break
            new_count = 0
            for r in reports:
                self.storage.append("reports", {
                    "type": "report_found",
                    "post_id": r["post_id"],
                    "category_id": category_id,
                    "category_name": category_name,
                    "title": r["title"],
                    "detail_url": r["detail_url"],
                    "thumbnail_url": r["thumbnail_url"],
                    "view_count": r["view_count"],
                    "publish_date": r["publish_date"],
                })
                new_count += 1
                self.log.ok(f"  report:{r['post_id']} {r['title'][:40]}")
            all_reports.extend(reports)
            if max_pages and page >= max_pages:
                break
            page += 1
            sleep_jitter(*REQUEST_DELAY)
        self.log.info(f"  Total reports for {category_name}: {len(all_reports)} ({new_count} new)")
        return all_reports

    def scrape_all_categories(self, max_pages: int = None, resume: bool = False):
        """Stage 2: Scrape report lists for all categories."""
        cat_lines = self.storage._read_lines("categories")
        if not cat_lines:
            self.scrape_categories()
            cat_lines = self.storage._read_lines("categories")
        total_cats = len(cat_lines)
        for i, line in enumerate(cat_lines, 1):
            cat = json.loads(line)
            cat_id = cat["category_id"]
            cat_name = cat["category_name"]
            if resume:
                existing = self.storage.get_category_report_count(cat_id)
                if existing > 0:
                    self.log.info(f"[{i}/{total_cats}] Skipping category:{cat_id} {cat_name} ({existing} reports already)")
                    continue
            self.log.info(f"[{i}/{total_cats}] Processing category:{cat_id} {cat_name}")
            self.scrape_category(cat_id, cat_name, max_pages=max_pages)

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
        matches = re.findall(r'https?://[^\s<>"'']+.zip', html, re.I)
        if matches:
            return matches[0]
        return None

    def visit_download_page(self, post_id: str) -> Tuple[bool, Optional[str], str]:
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
        if limit is not None:
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
