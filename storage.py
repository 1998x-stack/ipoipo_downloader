"""JSONL storage: append-only event log with state derivation.

采用追加写入的 JSONL 文件格式记录所有事件，状态通过每个实体的最后一个事件推导得出，
而非直接存储。这种设计的优势：
- 写入性能高：只需追加，无需更新或锁定已有记录。
- 数据完整性：即使进程崩溃，已有数据不会损坏。
- 事件溯源：完整保留所有历史事件，便于审计和调试。
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO


# 事件类型到推导状态的映射表
# 状态不是直接存储的，而是通过每个 post_id 的最后一个事件类型推导得出
STATUS_MAP: Dict[str, str] = {
    "report_found": "pending",
    "url_found": "ready",
    "download_started": "downloading",
    "download_completed": "downloaded",
    "download_failed": "failed",
}

# 文件键到实际文件名的映射
FILE_NAMES: Dict[str, str] = {
    "categories": "categories.jsonl",
    "reports": "reports.jsonl",
    "downloads": "downloads.jsonl",
}


class Storage:
    """基于 JSONL 的追加写入存储，支持去重、状态推导和按状态查询。

    设计原则：
    - 追加写入：所有事件只追加不修改，保证数据完整性。
    - 状态推导：实体的当前状态由该实体的最后一个事件类型决定。
    - 去重机制：通过 _seen_ids 集合在内存中跟踪已存在的 ID。
    - 线程安全：所有写入操作通过 threading.Lock 保护。
    """

    def __init__(self, data_dir: str) -> None:
        """初始化存储实例。

        Args:
            data_dir: JSONL 文件存储目录路径。
        """
        self.data_dir: Path = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._files: Dict[str, TextIO] = {}
        self._seen_ids: Dict[str, set] = {}
        self._lock: threading.Lock = threading.Lock()
        self._progress_path: Path = self.data_dir / "progress.json"
        self._progress: Dict[str, int] = self._load_progress()

    def _file_path(self, file_key: str) -> Path:
        """根据文件键获取对应的文件路径。

        Args:
            file_key: 文件键，如 "reports"、"categories"。

        Returns:
            对应的完整文件路径。
        """
        return self.data_dir / FILE_NAMES.get(file_key, f"{file_key}.jsonl")

    def _get_handle(self, file_key: str) -> TextIO:
        """获取或创建文件句柄。

        文件以追加模式打开，编码为 UTF-8。句柄会被缓存，避免重复打开。

        Args:
            file_key: 文件键。

        Returns:
            打开的文件句柄。
        """
        if file_key not in self._files:
            file_path = self._file_path(file_key)
            self._files[file_key] = open(
                file_path, "a", encoding="utf-8"
            )
        return self._files[file_key]

    def _load_seen_ids(self, file_key: str) -> None:
        """从 JSONL 文件中加载已有的 ID 集合，用于去重。

        优先使用 post_id，其次使用 category_id 作为唯一标识。
        解析失败的行会被静默跳过。

        Args:
            file_key: 文件键。
        """
        if file_key in self._seen_ids:
            return

        self._seen_ids[file_key] = set()
        file_path = self._file_path(file_key)

        if file_path.exists():
            for line in file_path.read_text(encoding="utf-8").splitlines():
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                try:
                    data = json.loads(stripped_line)
                    if "post_id" in data:
                        self._seen_ids[file_key].add(data["post_id"])
                    elif "category_id" in data:
                        self._seen_ids[file_key].add(data["category_id"])
                except json.JSONDecodeError:
                    continue

    def append(self, file_key: str, data: Dict[str, Any]) -> None:
        """追加一个事件到 JSONL 文件。

        使用 fsync 确保数据真正写入磁盘，而非仅停留在操作系统缓冲区。
        这对于防止进程崩溃时数据丢失至关重要。

        Args:
            file_key: 文件键，决定写入哪个 JSONL 文件。
            data: 事件数据字典，不能为空。

        Raises:
            ValueError: 当 data 为空字典时抛出。
        """
        if not data:
            raise ValueError("Cannot append empty data to JSONL file")

        with self._lock:
            self._load_seen_ids(file_key)
            file_handle = self._get_handle(file_key)
            file_handle.write(json.dumps(data, ensure_ascii=False) + "\n")
            file_handle.flush()
            os.fsync(file_handle.fileno())

            # 更新内存中的去重集合
            if "post_id" in data:
                self._seen_ids[file_key].add(data["post_id"])
            elif "category_id" in data:
                self._seen_ids[file_key].add(data["category_id"])

    def _read_lines(self, file_key: str) -> List[str]:
        """读取 JSONL 文件的所有非空行。

        Args:
            file_key: 文件键。

        Returns:
            非空行的列表，文件不存在时返回空列表。
        """
        file_path = self._file_path(file_key)
        if not file_path.exists():
            return []
        with open(file_path, encoding="utf-8") as file_handle:
            return [line for line in file_handle.readlines() if line.strip()]

    def get_state(self, file_key: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取实体的最后一个事件状态。

        遍历所有行，保留与 entity_id 匹配的最后一个事件。
        状态推导的核心方法：最后一个事件决定实体的当前状态。

        Args:
            file_key: 文件键。
            entity_id: 实体 ID（post_id 或 category_id）。

        Returns:
            最后一个匹配的事件字典，未找到时返回 None。
        """
        with self._lock:
            lines = self._read_lines(file_key)

        last_state: Optional[Dict[str, Any]] = None
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("post_id") == entity_id or data.get("category_id") == entity_id:
                    last_state = data
            except json.JSONDecodeError:
                continue

        return last_state

    def query_by_status(self, file_key: str, status: str) -> List[Dict[str, Any]]:
        """查询所有具有指定推导状态的实体。

        核心逻辑：
        1. 读取所有事件行和分类数据。
        2. 构建分类名称查找表，用于回填缺失的 category_name。
        3. 按 post_id 合并所有事件字段（后出现的事件覆盖先前的字段）。
        4. 根据最后一个事件的 type 推导状态，筛选匹配的记录。

        字段合并策略确保了 "unknown" 标题 bug 的修复：
        即使 url_found 事件不包含 title，合并后仍保留 report_found 中的 title。

        Args:
            file_key: 文件键。
            status: 目标状态，如 "pending"、"ready"、"downloaded"。

        Returns:
            匹配状态的实体状态列表。
        """
        with self._lock:
            report_lines = self._read_lines(file_key)
            category_lines = self._read_lines("categories")

        # 构建分类名称查找表
        category_names: Dict[str, str] = {}
        for line in category_lines:
            try:
                data = json.loads(line)
                if "category_id" in data:
                    category_names[data["category_id"]] = data.get(
                        "category_name", ""
                    )
            except json.JSONDecodeError:
                continue

        # 按 post_id 合并所有事件字段
        entity_states: Dict[str, Dict[str, Any]] = {}
        for line in report_lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    post_id = data["post_id"]
                    if post_id not in entity_states:
                        entity_states[post_id] = {}
                    entity_states[post_id].update(data)
            except json.JSONDecodeError:
                continue

        # 筛选匹配状态的实体
        results: List[Dict[str, Any]] = []
        for post_id, state in entity_states.items():
            derived_status = STATUS_MAP.get(state.get("type", ""), "")
            if derived_status == status:
                # 回填缺失的 category_name
                if "category_name" not in state and "category_id" in state:
                    state["category_name"] = category_names.get(
                        state["category_id"], ""
                    )
                results.append(state)

        return results

    def get_reports_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """获取指定分类下的所有报告（每个 post_id 取最新状态）。

        Args:
            category_id: 分类 ID。

        Returns:
            该分类下所有报告的最新状态列表。
        """
        with self._lock:
            report_lines = self._read_lines("reports")

        entity_states: Dict[str, Dict[str, Any]] = {}
        for line in report_lines:
            try:
                data = json.loads(line)
                if data.get("category_id") == category_id and "post_id" in data:
                    entity_states[data["post_id"]] = data
            except json.JSONDecodeError:
                continue

        return list(entity_states.values())

    def get_category_report_count(self, category_id: str) -> int:
        """统计指定分类下的唯一报告数量。

        Args:
            category_id: 分类 ID。

        Returns:
            唯一报告数量。
        """
        with self._lock:
            report_lines = self._read_lines("reports")

        post_ids: set = set()
        for line in report_lines:
            try:
                data = json.loads(line)
                if data.get("category_id") == category_id and "post_id" in data:
                    post_ids.add(data["post_id"])
            except json.JSONDecodeError:
                continue

        return len(post_ids)

    def is_report_downloaded(self, post_id: str) -> bool:
        """检查报告是否已成功下载。

        Args:
            post_id: 报告 ID。

        Returns:
            如果最后一个事件是 download_completed 则返回 True。
        """
        state = self.get_state("reports", post_id)
        return state is not None and state.get("type") == "download_completed"

    def get_stats(self) -> Dict[str, Any]:
        """获取整体统计信息。

        Returns:
            包含 total_categories、total_reports、total_downloads 和
            by_status 的统计字典。文件为空时返回零值统计。
        """
        with self._lock:
            category_lines = self._read_lines("categories")
            report_lines = self._read_lines("reports")

        stats: Dict[str, Any] = {
            "total_categories": 0,
            "total_reports": 0,
            "total_downloads": 0,
            "by_status": {},
        }

        # 分类数量
        stats["total_categories"] = len(category_lines)

        # 按 post_id 合并报告状态
        entity_states: Dict[str, Dict[str, Any]] = {}
        for line in report_lines:
            try:
                data = json.loads(line)
                if "post_id" in data:
                    entity_states[data["post_id"]] = data
            except json.JSONDecodeError:
                continue

        stats["total_reports"] = len(entity_states)

        # 按状态计数
        status_counts: Dict[str, int] = {}
        for state in entity_states.values():
            derived_status = STATUS_MAP.get(state.get("type", ""), "unknown")
            status_counts[derived_status] = status_counts.get(derived_status, 0) + 1
        stats["by_status"] = status_counts

        # 已下载数量
        downloaded_count = sum(
            1
            for state in entity_states.values()
            if state.get("type") == "download_completed"
        )
        stats["total_downloads"] = downloaded_count

        return stats

    def _load_progress(self) -> Dict[str, int]:
        """加载进度检查点数据。

        Returns:
            分类 ID 到页码的映射字典，加载失败时返回空字典。
        """
        if self._progress_path.exists():
            try:
                return json.loads(self._progress_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def save_progress(self, category_id: str, page: int) -> None:
        """保存进度检查点。

        使用锁保护，防止并发写入导致数据损坏。

        Args:
            category_id: 分类 ID。
            page: 当前已完成的页码。
        """
        with self._lock:
            self._progress[category_id] = page
            self._progress_path.write_text(json.dumps(self._progress))

    def get_progress(self, category_id: str) -> int:
        """获取指定分类的进度检查点。

        Args:
            category_id: 分类 ID。

        Returns:
            已完成的页码，未找到时返回 0。
        """
        return self._progress.get(category_id, 0)

    def close(self) -> None:
        """关闭所有打开的文件句柄。"""
        for file_handle in self._files.values():
            file_handle.close()
        self._files.clear()
