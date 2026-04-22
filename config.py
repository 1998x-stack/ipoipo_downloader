"""Configuration for ipoipo downloader.

This module centralizes all configuration constants used across the pipeline,
including directory paths, URL templates, category mappings, request/proxy
settings, and logging parameters.

Directories are created on import to ensure they exist before any stage runs.
"""
import os
from pathlib import Path
from typing import Dict, Tuple

# =============================================================================
# 路径常量 — 项目根目录及数据/日志目录
# 导入时自动创建目录，确保后续阶段无需重复检查
# =============================================================================
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
DOWNLOAD_DIR: Path = DATA_DIR / "downloads"
LOG_DIR: Path = BASE_DIR / "logs"

for directory in [DATA_DIR, DOWNLOAD_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============================================================================
# URL 模板 — ipoipo 网站各页面的 URL 构造规则
# BASE_URL: 网站首页
# CATEGORY_PAGE_URL: 分类首页（单页）
# CATEGORY_PAGE_PAGINATED: 分类分页（第 N 页）
# POST_URL: 文章详情页
# DOWNLOAD_URL: 下载页（用于获取 ZIP 直链）
# ZIP_HOST: ZIP 文件托管域名（阿里云 CDN，有 Referer ACL）
# =============================================================================
BASE_URL: str = "https://ipoipo.cn"
CATEGORY_PAGE_URL: str = "https://ipoipo.cn/tags-{}.html"
CATEGORY_PAGE_PAGINATED: str = "https://ipoipo.cn/tags-{}_{}.html"
POST_URL: str = "https://ipoipo.cn/post/{}.html"
DOWNLOAD_URL: str = "https://ipoipo.cn/download/{}.html"
ZIP_HOST: str = "https://ipo.ai-tag.cn"

# =============================================================================
# 分类映射 — 分类 ID 到中文名称
# 用于下载目录命名和日志输出
# =============================================================================
CATEGORY_NAMES: Dict[str, str] = {
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

# =============================================================================
# 请求设置 — 控制爬虫请求频率和重试策略
# REQUEST_DELAY: 两次请求间的随机延迟范围（秒），防止触发反爬
# MAX_RETRIES: 单个请求最大重试次数
# RETRY_DELAY: 重试间隔（秒）
# DOWNLOAD_TIMEOUT: 下载超时（秒），ZIP 文件可能较大
# REQUEST_TIMEOUT: 普通 HTTP 请求超时（秒）
# =============================================================================
REQUEST_DELAY: Tuple[int, int] = (1, 3)
MAX_RETRIES: int = 3
RETRY_DELAY: float = 1.5
DOWNLOAD_TIMEOUT: int = 300
REQUEST_TIMEOUT: int = 30

# =============================================================================
# 代理设置 — Clash 代理配置
# PROXY_CONFIG_PATH: Clash YAML 配置文件路径（被 gitignore）
# PROXY_TEST_TIMEOUT: 代理节点连通性测试超时（秒）
# PROXY_MAX_LATENCY: 节点最大可接受延迟（毫秒）
# USE_PROXY: 是否启用代理，可通过环境变量 USE_PROXY=false 覆盖
# =============================================================================
PROXY_CONFIG_PATH: Path = BASE_DIR / "config" / "proxy.yaml"
PROXY_TEST_TIMEOUT: int = 3
PROXY_MAX_LATENCY: int = 500
USE_PROXY: bool = os.getenv("USE_PROXY", "true").lower() == "true"

# =============================================================================
# 下载设置 — ZIP 下载和文件处理参数
# CHUNK_SIZE: 流式下载的块大小（字节）
# KEEP_ZIP: 解压后是否保留原始 ZIP 文件
# MAX_FILENAME_LENGTH: 文件名最大长度，防止超长文件名
# MIN_VALID_FILE_SIZE: 最小有效文件大小（字节），过滤空文件/错误响应
# =============================================================================
CHUNK_SIZE: int = 8192
KEEP_ZIP: bool = False
MAX_FILENAME_LENGTH: int = 200
MIN_VALID_FILE_SIZE: int = 1024

# =============================================================================
# 日志设置 — 事件日志文件路径
# =============================================================================
LOG_FILE: Path = LOG_DIR / "events.jsonl"
