"""Downloader: Stage 4 — ZIP download, extract, rename."""
import os
import zipfile
from pathlib import Path
from typing import Tuple
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
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    # Prevent path traversal
                    if ".." in name or name.startswith("/"):
                        self.log.warn(f"Skipping suspicious ZIP entry: {name}")
                        continue
                    clean = clean_filename(name)
                    target = extract_dir / clean
                    # Ensure target stays within extract_dir
                    target.resolve().relative_to(extract_dir.resolve())
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

        if not zip_url:
            self.log.warn(f"No download URL for {post_id}")
            return False

        # Check storage state first
        if self.storage.is_report_downloaded(post_id):
            # Verify file actually exists on disk
            doc_pattern = f"_{clean_filename(title)}"
            cat_dir_check = self.get_category_dir(category_id, category_name)
            existing_check = list(cat_dir_check.glob(f"*{doc_pattern[:30]}*"))
            if existing_check and any(f.stat().st_size > MIN_VALID_FILE_SIZE for f in existing_check):
                self.log.info(f"Already downloaded (verified): {post_id} {title[:40]}")
                return True
            self.log.warn(f"Storage says downloaded but file missing, re-downloading: {post_id}")

        download_page_url = self.get_download_page_url(post_id)
        cat_dir = self.get_category_dir(category_id, category_name)
        zip_filename = os.path.basename(urlparse(zip_url).path)
        zip_path = cat_dir / clean_filename(zip_filename)

        # Check if file already exists on disk
        doc_pattern = f"{extract_timestamp_from_zip(zip_filename)}_{clean_filename(title)}"
        existing = list(cat_dir.glob(f"{doc_pattern[:20]}*"))
        if existing:
            for f in existing:
                if f.stat().st_size > MIN_VALID_FILE_SIZE:
                    self.log.info(f"Already downloaded (disk): {f.name}")
                    # Update storage state to match
                    self.storage.append("reports", {
                        "type": "download_completed",
                        "post_id": post_id,
                        "category_id": category_id,
                        "category_name": category_name,
                        "file_path": str(cat_dir),
                        "file_size": f.stat().st_size,
                    })
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
                    if self._consecutive_failures >= 2:
                        self._switch_proxy_and_retry()
                        self._consecutive_failures = 0
                        continue
                    if self._switch_proxy_and_retry():
                        self._consecutive_failures = 0
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
                "category_id": category_id,
                "category_name": category_name,
                "file_path": str(cat_dir),
                "file_size": size,
            })
            self._consecutive_failures = 0
            return True

        self.log.error(f"All attempts failed for {post_id}")
        return False

    def download_all_ready(self, max_reports: int = None, keep_zip: bool = KEEP_ZIP, reports: list = None) -> dict:
        self.log.info("Stage 4: Downloading all ready reports")
        ready = reports if reports is not None else self.storage.query_by_status("reports", "ready")
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

    def extract_downloaded_zips(self, max_reports: int = None, keep_zip: bool = True, category: str = None):
        self.log.info("Extracting downloaded ZIPs")
        zips = list(DOWNLOAD_DIR.rglob("*.zip"))
        if category:
            zips = [z for z in zips if z.parent.name.startswith(f"{category}_")]
            self.log.info(f"Filtered to category {category}: {len(zips)} ZIPs")
        if max_reports:
            zips = zips[:max_reports]
        for zip_path in zips:
            # Try to find report title from storage
            title = zip_path.stem
            state = self.storage.get_state("reports", title)
            if state and "title" in state:
                title = state["title"]
            if self._extract_zip(zip_path, zip_path.parent, title):
                self.log.ok(f"Extracted: {zip_path.name}")
                if not keep_zip:
                    zip_path.unlink()
            else:
                self.log.error(f"Failed to extract: {zip_path.name}")
