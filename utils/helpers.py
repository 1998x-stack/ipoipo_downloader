"""Common helpers: retry decorator, jitter sleep, URL helpers.

Provides reusable utilities for network request resilience (exponential
backoff retry), randomized delays (jitter sleep to avoid thundering herd),
and URL parsing (post ID extraction, validity check).
"""

import time
import random
import functools
import re
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential backoff.

    On each failure, the delay is multiplied by ``backoff`` before the
    next attempt. Formula: ``delay * (backoff ** (attempt - 1))``.

    重试退避公式：第 n 次失败后等待 delay * backoff^(n-1) 秒。
    例如 delay=1, backoff=2 时，等待序列为 1s → 2s → 4s → ...
    这种指数退避可在服务端限流时避免加剧负载。

    Args:
        max_attempts: Total number of attempts (including the first).
            Must be >= 1.
        delay: Initial delay in seconds before the first retry.
            Must be >= 0.
        backoff: Multiplier applied to delay after each retry.
            Must be >= 1.0.

    Returns:
        A decorator that wraps the target function with retry logic.

    Raises:
        The last exception raised by the wrapped function if all
        attempts fail. ``KeyboardInterrupt`` and ``SystemExit`` are
        never caught and propagate immediately.

    Examples:
        >>> @retry(max_attempts=3, delay=0.1, backoff=2.0)
        ... def flaky(): ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay: float = delay
            last_exception: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as e:
                    last_exception = e
                    # 非最后一次尝试时等待后重试
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def sleep_jitter(low: float, high: float) -> None:
    """Sleep for a random duration between ``low`` and ``high`` seconds.

    使用均匀分布的随机延迟，避免多个客户端同时发起请求造成的
    "惊群效应"（thundering herd），从而降低被服务端识别为爬虫的概率。

    Args:
        low: Minimum sleep duration in seconds.
        high: Maximum sleep duration in seconds.

    Examples:
        >>> sleep_jitter(0.5, 1.5)  # sleeps between 0.5 and 1.5 seconds
    """
    time.sleep(random.uniform(low, high))


def extract_post_id(url: str) -> str:
    """Extract the numeric post ID from an ipoipo URL.

    Matches the pattern ``/post/{digits}.html`` anywhere in the URL.

    从 URL 中提取文章 ID，匹配形如 /post/26028.html 的路径片段。
    若未找到匹配则返回空字符串，不会抛出异常。

    Args:
        url: The full URL string. If empty or non-matching, returns "".

    Returns:
        The post ID as a string (e.g., ``"26028"``), or ``""`` if not found.

    Examples:
        >>> extract_post_id("https://ipoipo.cn/post/26028.html")
        '26028'
        >>> extract_post_id("https://example.com")
        ''
    """
    if not url:
        return ""
    match = re.search(r"/post/(\d+)\.html", url)
    return match.group(1) if match else ""


def is_valid_url(url: str) -> bool:
    """Check whether a string is a well-formed URL with scheme and host.

    使用 urlparse 解析 URL，要求同时包含 scheme（如 https）
    和 netloc（域名），两者缺一不可。

    Args:
        url: The string to validate. Empty strings and non-strings
            are treated as invalid.

    Returns:
        ``True`` if the URL has both a scheme and a network location,
        ``False`` otherwise.

    Examples:
        >>> is_valid_url("https://example.com/path")
        True
        >>> is_valid_url("not-a-url")
        False
        >>> is_valid_url("")
        False
    """
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
