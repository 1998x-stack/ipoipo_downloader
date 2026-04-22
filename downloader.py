"""Downloader: Stage 4 — ZIP download, extract, rename.

负责下载 ZIP 文件、解压文档并重命名。关键设计：
- 反热链保护绕过：ZIP 文件托管在 ipo.ai-tag.cn（阿里云 CDN），需要有效的 Referer。
  必须先访问下载页面建立 session cookies，再携带 Referer 下载 ZIP。
- Content-Type 验证：防止 CDN 返回 HTML 错误页面（静默 403）。
- 代理切换重试：连续失败时自动切换代理节点并重试。
- 路径遍历保护：解压时防止恶意 ZIP 文件写入系统目录。
"""

import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from config import (
    CHUNK_SIZE,
    DOWNLOAD_DIR,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_URL,
    KEEP_ZIP,
    MIN_VALID_FILE_SIZE,
    REQUEST_TIMEOUT,
    USE_PROXY,
)
from utils.headers import get_browser_headers, get_download_headers
from utils.sanitize import (
    clean_filename,
    clean_foldername,
    extract_timestamp_from_zip,
    generate_doc_filename,
)
from utils.helpers import sleep_jitter


class Downloader:
    """ZIP 下载器，支持反热链绕过、代理切换和自动解压。

    下载流程：
    1. 访问下载页面建立 session cookies。
    2. 等待 0.5-1 秒模拟人类行为。
    3. 携带 Referer 头下载 ZIP 文件。
    4. 验证 Content-Type 不是 text/html（防止静默 403）。
    5. 解压 ZIP 并重命名文档。
    """

    def __init__(
        self,
        storage: Any,
        log: Any,
        use_proxy: bool = USE_PROXY,
        proxy_manager: Optional[Any] = None,
    ) -> None:
        """初始化下载器。

        Args:
            storage: Storage 实例，用于查询和更新下载状态。
            log: Logger 实例，用于日志输出。
            use_proxy: 是否启用代理，默认从配置读取。
            proxy_manager: ProxyManager 实例，用于代理切换。
        """
        self.storage: Any = storage
        self.log: Any = log
        self.use_proxy: bool = use_proxy
        self.proxy_manager: Optional[Any] = proxy_manager
        self.session: requests.Session = requests.Session()
        self.session.headers.update(get_browser_headers())

        if use_proxy and proxy_manager is not None:
            self.session.proxies.update(proxy_manager.get_local_proxy())

        self._consecutive_failures: int = 0

    def close(self) -> None:
        """关闭 HTTP 会话，释放连接资源。"""
        self.session.close()

    def get_download_page_url(self, post_id: str) -> str:
        """构造报告下载页面的 URL。

        Args:
            post_id: 报告 ID。

        Returns:
            完整的下载页面 URL。
        """
        return DOWNLOAD_URL.format(post_id)

    def get_category_dir(self, category_id: str, category_name: str) -> Path:
        """获取或创建分类目录。

        目录格式为 "{category_id}_{ sanitized_category_name }"。

        Args:
            category_id: 分类 ID。
            category_name: 分类名称（中文）。

        Returns:
            分类目录的 Path 对象。
        """
        folder_name = f"{category_id}_{clean_foldername(category_name)}"
        dir_path = DOWNLOAD_DIR / folder_name
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def generate_filename(self, zip_filename: str, report_title: str) -> str:
        """根据 ZIP 文件名和报告标题生成文档文件名。

        Args:
            zip_filename: 原始 ZIP 文件名。
            report_title: 报告标题。

        Returns:
            格式化后的文档文件名，格式为 "{YYYYMMDD}_{标题}_{页数}页.{ext}"。
        """
        return generate_doc_filename(zip_filename, report_title)

    def _download_zip(
        self, zip_url: str, referer: str, save_path: Path
    ) -> Tuple[bool, int]:
        """下载 ZIP 文件，携带 Referer 头以绕过反热链保护。

        Args:
            zip_url: ZIP 文件的直接下载 URL。
            referer: Referer 头，通常为下载页面 URL。
            save_path: 文件保存路径。

        Returns:
            (是否成功, 文件大小（字节）)。
        """
        # 边界检查：空 URL 直接返回失败
        if not zip_url:
            self.log.error("Empty ZIP URL")
            return False, 0

        try:
            headers = get_download_headers(referer)
            response = self.session.get(
                zip_url, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT
            )

            if response.status_code == 403:
                self.log.error(f"403 Forbidden: {zip_url}")
                return False, 0

            response.raise_for_status()

            # 验证 Content-Type：防止 CDN 返回 HTML 错误页面（静默 403）
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower() and zip_url.endswith(".zip"):
                self.log.error("Received HTML instead of ZIP")
                return False, 0

            save_path.parent.mkdir(parents=True, exist_ok=True)
            file_size = 0
            with open(save_path, "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        file_handle.write(chunk)
                        file_size += len(chunk)

            return True, file_size
        except Exception as exc:
            self.log.error(f"Download failed: {exc}")
            return False, 0

    def _extract_zip(
        self, zip_path: Path, extract_dir: Path, report_title: str
    ) -> bool:
        """解压 ZIP 文件并重命名文档。

        路径遍历保护：
        1. 检查文件名中是否包含 ".." 或以 "/" 开头。
        2. 使用 resolve().relative_to() 确保解压路径在目标目录内。
        这是为了防止恶意 ZIP 文件将文件写入系统目录（如 /etc/passwd）。

        Args:
            zip_path: ZIP 文件路径。
            extract_dir: 解压目标目录。
            report_title: 报告标题，用于重命名文档。

        Returns:
            解压是否成功。
        """
        try:
            if not zipfile.is_zipfile(zip_path):
                self.log.error(f"Invalid ZIP: {zip_path}")
                return False

            with zipfile.ZipFile(zip_path, "r") as zip_file:
                for entry_name in zip_file.namelist():
                    # 防止路径遍历攻击：检查 ".." 和绝对路径
                    if ".." in entry_name or entry_name.startswith("/"):
                        self.log.warn(f"Skipping suspicious ZIP entry: {entry_name}")
                        continue

                    sanitized_name = clean_filename(entry_name)
                    target_path = extract_dir / sanitized_name

                    # 确保目标路径在 extract_dir 内部，防止路径遍历
                    target_path.resolve().relative_to(extract_dir.resolve())
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    with zip_file.open(entry_name) as source, open(
                        target_path, "wb"
                    ) as dest:
                        dest.write(source.read())

                    # 对文档文件重命名为统一格式
                    if target_path.suffix.lower() in {
                        ".pdf",
                        ".docx",
                        ".doc",
                        ".pptx",
                        ".ppt",
                        ".xlsx",
                        ".xls",
                    }:
                        new_name = generate_doc_filename(zip_path.name, report_title)
                        new_path = extract_dir / clean_filename(new_name)
                        if new_path != target_path:
                            target_path.rename(new_path)
                            self.log.ok(f"  Renamed: {sanitized_name} → {new_path.name}")

            return True
        except Exception as exc:
            self.log.error(f"Extraction failed: {exc}")
            return False

    def _switch_proxy_and_retry(self) -> bool:
        """切换代理节点并重试。

        流程：
        1. 调用 proxy_manager.switch_node() 选择新节点。
        2. 更新 session 的代理配置。
        3. 清除 cookies（防止旧节点的 session 污染）。
        4. 等待 1-2 秒后重试。

        Returns:
            代理切换是否成功。
        """
        if self.proxy_manager is not None:
            self.log.warn("Switching proxy node...")
            if self.proxy_manager.switch_node():
                self.session.proxies.update(self.proxy_manager.get_local_proxy())
                self.session.cookies.clear()
                sleep_jitter(1, 2)
                return True
        return False

    def download_report(self, report: Dict[str, Any], keep_zip: bool = KEEP_ZIP) -> bool:
        """下载单个报告，包含重试、代理切换和去重检查。

        下载流程：
        1. 检查存储状态和磁盘文件，避免重复下载。
        2. 访问下载页面建立 session cookies。
        3. 等待 0.5-1 秒模拟人类行为。
        4. 下载 ZIP 文件，验证 Content-Type。
        5. 解压并重命名文档。
        6. 更新存储状态为 download_completed。

        重试策略：
        - 最多尝试 3 次。
        - 连续失败 2 次后自动切换代理节点。
        - 切换代理后重置失败计数器。

        Args:
            report: 报告数据字典，必须包含 post_id，可选 title、download_url、
                category_id、category_name。
            keep_zip: 解压后是否保留 ZIP 文件。

        Returns:
            下载是否成功。
        """
        post_id = report["post_id"]
        title = report.get("title", "unknown")
        zip_url = report.get("download_url", "")
        category_id = report.get("category_id", "0")
        category_name = report.get("category_name", "unknown")

        if not zip_url:
            self.log.warn(f"No download URL for {post_id}")
            return False

        # 检查存储状态：如果已下载，验证磁盘文件是否存在
        if self.storage.is_report_downloaded(post_id):
            doc_pattern = f"_{clean_filename(title)}"
            cat_dir_check = self.get_category_dir(category_id, category_name)
            existing_files = list(cat_dir_check.glob(f"*{doc_pattern[:30]}*"))
            if existing_files and any(
                file_entry.stat().st_size > MIN_VALID_FILE_SIZE
                for file_entry in existing_files
            ):
                self.log.info(f"Already downloaded (verified): {post_id} {title[:40]}")
                return True
            self.log.warn(
                f"Storage says downloaded but file missing, re-downloading: {post_id}"
            )

        download_page_url = self.get_download_page_url(post_id)
        cat_dir = self.get_category_dir(category_id, category_name)
        zip_filename = os.path.basename(urlparse(zip_url).path)
        zip_path = cat_dir / clean_filename(zip_filename)

        # 检查磁盘上是否已有匹配的文件
        doc_pattern = f"{extract_timestamp_from_zip(zip_filename)}_{clean_filename(title)}"
        existing_files = list(cat_dir.glob(f"{doc_pattern[:20]}*"))
        if existing_files:
            for file_entry in existing_files:
                if file_entry.stat().st_size > MIN_VALID_FILE_SIZE:
                    self.log.info(f"Already downloaded (disk): {file_entry.name}")
                    # 更新存储状态以匹配磁盘文件
                    self.storage.append(
                        "reports",
                        {
                            "type": "download_completed",
                            "post_id": post_id,
                            "category_id": category_id,
                            "category_name": category_name,
                            "file_path": str(cat_dir),
                            "file_size": file_entry.stat().st_size,
                        },
                    )
                    return True

        self.log.info(f"Downloading: {title[:40]}")

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                self.log.info(f"  Attempt {attempt}/{max_attempts}")

            # 访问下载页面建立 session cookies（反热链绕过的关键步骤）
            try:
                self.session.get(
                    download_page_url,
                    headers=get_browser_headers(),
                    timeout=REQUEST_TIMEOUT,
                )
                sleep_jitter(0.5, 1.0)
            except Exception as exc:
                self.log.warn(f"Failed to visit download page: {exc}")

            download_success, file_size = self._download_zip(
                zip_url, download_page_url, zip_path
            )

            if not download_success:
                self._consecutive_failures += 1
                if attempt < max_attempts:
                    # 连续失败 2 次后切换代理
                    if self._consecutive_failures >= 2:
                        self._switch_proxy_and_retry()
                        self._consecutive_failures = 0
                        continue
                    if self._switch_proxy_and_retry():
                        self._consecutive_failures = 0
                        continue
                self.log.error(f"Download failed: {post_id}")
                self.storage.append(
                    "reports",
                    {
                        "type": "download_failed",
                        "post_id": post_id,
                        "error": f"attempt {attempt}",
                    },
                )
                return False

            # 验证文件大小：太小的文件可能是错误响应
            if file_size < MIN_VALID_FILE_SIZE:
                self.log.error(f"Downloaded file too small: {file_size} bytes")
                if zip_path.exists():
                    zip_path.unlink()
                continue

            self.log.ok(f"Downloaded: {zip_filename} ({file_size / 1024:.1f} KB)")

            # 解压 ZIP 文件
            if self._extract_zip(zip_path, cat_dir, title):
                self.log.ok(f"Extracted: {title[:40]}")
                if not keep_zip and zip_path.exists():
                    zip_path.unlink()
            else:
                self.log.warn(f"Extraction failed, keeping ZIP: {zip_path.name}")

            # 更新存储状态为已下载
            self.storage.append(
                "reports",
                {
                    "type": "download_completed",
                    "post_id": post_id,
                    "category_id": category_id,
                    "category_name": category_name,
                    "file_path": str(cat_dir),
                    "file_size": file_size,
                },
            )
            self._consecutive_failures = 0
            return True

        self.log.error(f"All attempts failed for {post_id}")
        return False

    def download_all_ready(
        self,
        max_reports: Optional[int] = None,
        keep_zip: bool = KEEP_ZIP,
        reports: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, int]:
        """下载所有状态为 "ready" 的报告。

        Args:
            max_reports: 最大下载数量，None 表示不限制。
            keep_zip: 解压后是否保留 ZIP 文件。
            reports: 预过滤的报告列表，None 时从存储中查询 ready 状态的报告。

        Returns:
            统计字典，包含 success 和 failed 计数。
        """
        self.log.info("Stage 4: Downloading all ready reports")

        ready_reports = (
            reports if reports is not None else self.storage.query_by_status("reports", "ready")
        )

        if max_reports is not None:
            ready_reports = ready_reports[:max_reports]

        self.log.info(f"  Ready reports: {len(ready_reports)}")

        stats: Dict[str, int] = {"success": 0, "failed": 0}
        for index, report in enumerate(ready_reports):
            self.log.info(f"  [{index + 1}/{len(ready_reports)}]")
            if self.download_report(report, keep_zip=keep_zip):
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # 最后一个报告不需要等待
            if index < len(ready_reports) - 1:
                sleep_jitter(1.5, 2.5)

        self.log.info(
            f"  Stage 4 complete: {stats['success']} success, {stats['failed']} failed"
        )
        return stats

    def extract_downloaded_zips(
        self,
        max_reports: Optional[int] = None,
        keep_zip: bool = True,
        category: Optional[str] = None,
    ) -> None:
        """提取已下载的 ZIP 文件。

        Args:
            max_reports: 最大提取数量，None 表示不限制。
            keep_zip: 提取后是否保留 ZIP 文件。
            category: 过滤特定分类，None 表示处理所有分类。
        """
        self.log.info("Extracting downloaded ZIPs")

        zip_files: List[Path] = list(DOWNLOAD_DIR.rglob("*.zip"))

        if category is not None:
            zip_files = [
                zip_path
                for zip_path in zip_files
                if zip_path.parent.name.startswith(f"{category}_")
            ]
            self.log.info(f"Filtered to category {category}: {len(zip_files)} ZIPs")

        if max_reports is not None:
            zip_files = zip_files[:max_reports]

        # 边界检查：无 ZIP 文件时直接返回
        if not zip_files:
            self.log.info("No ZIP files found to extract")
            return

        for zip_path in zip_files:
            # 尝试从存储中获取报告标题
            title = zip_path.stem
            state = self.storage.get_state("reports", title)
            if state is not None and "title" in state:
                title = state["title"]

            if self._extract_zip(zip_path, zip_path.parent, title):
                self.log.ok(f"Extracted: {zip_path.name}")
                if not keep_zip:
                    zip_path.unlink()
            else:
                self.log.error(f"Failed to extract: {zip_path.name}")
