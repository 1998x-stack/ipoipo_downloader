"""Optional periodic runner that does not overlap runs."""
import threading
from collections.abc import Callable


class Scheduler:
    def __init__(self, run_once: Callable[[], None], interval_seconds: float):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.run_once = run_once
        self.interval_seconds = interval_seconds

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            self.run_once()
            stop.wait(self.interval_seconds)
