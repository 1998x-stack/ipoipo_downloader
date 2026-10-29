"""Explicit bounded retry policy for listing fetches."""
import time
from collections.abc import Callable
from typing import TypeVar

from ipoipo.transport.http import FetchError

T = TypeVar("T")


def with_retries(action: Callable[[], T], max_attempts: int = 3) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except FetchError as exc:
            if not exc.retryable or attempt == max_attempts:
                raise
            time.sleep(min(10, 2 ** (attempt - 1)))
    raise AssertionError("unreachable")
