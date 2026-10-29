"""Global per-client request pacing, not a bot-detection circumvention mechanism."""
import threading
import time


class RateLimiter:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            delay = max(0.0, self._next - time.monotonic())
            if delay:
                time.sleep(delay)
            self._next = time.monotonic() + self.interval
