"""Common helpers: retry, jitter sleep, URL helpers."""
import time
import random
import functools
from urllib.parse import urljoin, urlparse
import re


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        return wrapper
    return decorator


def sleep_jitter(low: float, high: float):
    """Sleep for a random duration between low and high seconds."""
    time.sleep(random.uniform(low, high))


def extract_post_id(url: str) -> str:
    """Extract post_id from URL like https://ipoipo.cn/post/26028.html."""
    match = re.search(r"/post/(\d+)\.html", url)
    return match.group(1) if match else ""


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
