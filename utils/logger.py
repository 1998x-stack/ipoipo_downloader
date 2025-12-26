"""
日志配置模块
"""
import sys
from loguru import logger
from config.settings import LOG_DIR, LOG_LEVEL, LOG_ROTATION, LOG_RETENTION

# 移除默认的handler
logger.remove()

# 添加控制台输出（带颜色）
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL,
    colorize=True
)

# 添加文件输出（完整日志）
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation=LOG_ROTATION,
    retention=LOG_RETENTION,
    compression="zip",
    encoding="utf-8"
)

# 添加错误日志
logger.add(
    LOG_DIR / "error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation=LOG_ROTATION,
    retention=LOG_RETENTION,
    compression="zip",
    encoding="utf-8"
)

def get_logger(name: str = None):
    """获取logger实例"""
    if name:
        return logger.bind(name=name)
    return logger