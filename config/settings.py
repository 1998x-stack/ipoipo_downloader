"""
配置管理模块
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# ===== 代理配置 =====
CLASH_CONFIG_PATH = BASE_DIR / "config" / "clash_config.yaml"
USE_PROXY = True  # 是否使用代理
PROXY_TEST_TIMEOUT = 3  # 代理测速超时时间（秒）
PROXY_MAX_RETRIES = 1  # 代理重试次数

# ===== 数据库配置 =====
DATABASE_PATH = BASE_DIR / "data" / "downloads.db"
DATABASE_PATH.parent.mkdir(exist_ok=True)

# ===== 下载配置 =====
DOWNLOAD_DIR = BASE_DIR / "data" / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 8192  # 下载块大小（字节）
DOWNLOAD_TIMEOUT = 60  # 下载超时时间（秒）
MAX_CONCURRENT_DOWNLOADS = 3  # 最大并发下载数

# ===== 爬虫配置 =====
REQUEST_DELAY = (1, 3)  # 请求延迟范围（秒）
MAX_RETRIES = 1  # 最大重试次数
RETRY_DELAY = 1.5  # 重试延迟（秒）

# ===== 日志配置 =====
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = "INFO"
LOG_ROTATION = "10 MB"  # 日志文件大小
LOG_RETENTION = "30 days"  # 日志保留时间

# ===== 目标网站配置 =====
BASE_URL = "https://ipoipo.cn"
CATEGORY_PAGE_URL = "https://ipoipo.cn/tags-{}.html"  # 分类页
CATEGORY_PAGE_PAGINATED = "https://ipoipo.cn/tags-{}_{}.html"  # 分类页（分页）
POST_URL = "https://ipoipo.cn/post/{}.html"  # 文章页
DOWNLOAD_URL = "https://ipoipo.cn/download/{}.html"  # 下载页

# ===== 文件命名配置 =====
INVALID_CHARS = r'<>:"/\|?*'  # Windows文件名非法字符
MAX_FILENAME_LENGTH = 200  # 最大文件名长度

# ===== 分类映射（用于创建友好的文件夹名称）=====
CATEGORY_NAMES = {
    "70": "TMT行业",
    "53": "医药医疗器械",
    "59": "金融行业",
    "69": "新能源及电力",
    "14": "电子行业",
    "10": "智能制造",
    "79": "汽车行业",
    "67": "地产及旅游",
    "34": "经济报告",
    "24": "新材料及矿产",
    "61": "电商及销售",
    "62": "消费者及人群研究",
    "33": "食品饮料酒水",
    "11": "大消费",
    "85": "人工智能AI",
    "60": "化工行业",
    "63": "物流行业",
    "7": "教育行业",
    "23": "云计算行业",
    "56": "节能环保",
    "64": "农林牧渔",
    "73": "餐饮业",
    "74": "化妆品行业",
    "25": "体育及用品",
    "68": "军工行业",
    "76": "光电行业",
    "39": "纺织服装",
    "86": "航天通讯",
    "77": "安全监控",
    "66": "服务业",
    "84": "宠物行业",
    "75": "奢侈品及珠宝",
    "72": "经验干货",
    "83": "母婴行业",
    "80": "检测行业",
    "82": "共享经济",
    "88": "新基建",
    "54": "博彩行业",
}