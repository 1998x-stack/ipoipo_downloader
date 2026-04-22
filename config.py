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
# Default: proxy enabled. Override via USE_PROXY=false env or --no-proxy CLI flag.
PROXY_CONFIG_PATH = BASE_DIR / "config" / "proxy.yaml"
PROXY_TEST_TIMEOUT = 3
PROXY_MAX_LATENCY = 500
USE_PROXY = os.getenv("USE_PROXY", "true").lower() == "true"

# Download settings
CHUNK_SIZE = 8192
KEEP_ZIP = False
MAX_FILENAME_LENGTH = 200
MIN_VALID_FILE_SIZE = 1024  # bytes

# Logging
LOG_FILE = LOG_DIR / "events.jsonl"
