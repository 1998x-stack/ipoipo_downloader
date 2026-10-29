"""One-at-a-time, atomically claimed work; failures never spin indefinitely."""
import logging
import threading
from dataclasses import dataclass
from typing import Callable

from ipoipo.domain.models import Task
from ipoipo.artifacts.validator import ArtifactError
from ipoipo.sources.ipoipo_cn.parser import ParseError
from ipoipo.persistence.repository import Repository


@dataclass
class WorkerResult:
    succeeded: int = 0
    retry_wait: int = 0
    failed: int = 0

    @property
    def attempted(self) -> int:
        return self.succeeded + self.retry_wait + self.failed


def drain_stage(repository: Repository, stage: str, owner: str,
                action: Callable[[Task], None], *, limit: int | None,
                lease_seconds: int, category_id: str | None = None) -> WorkerResult:
    result = WorkerResult()
    while limit is None or result.attempted < limit:
        tasks = repository.claim(stage, owner, limit=1, lease_seconds=lease_seconds,
                                 category_id=category_id)
        if not tasks:
            break  # future retry_wait work is left for the next run, not busy-spun
        task = tasks[0]
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            interval = max(0.5, min(30.0, lease_seconds / 3))
            while not stop_heartbeat.wait(interval):
                try:
                    repository.renew_lease(task, lease_seconds)
                except RuntimeError:
                    break

        thread = threading.Thread(target=heartbeat, name=f"lease-{task.id}", daemon=True)
        thread.start()
        try:
            action(task)
            result.succeeded += 1
        except Exception as exc:
            retryable = getattr(exc, "retryable", not isinstance(exc, (ValueError, PermissionError, ArtifactError, ParseError)))
            logging.getLogger(__name__).warning("task failed: stage=%s post=%s reason=%s",
                                                stage, task.post_id, exc)
            outcome = repository.failed(task, str(exc), retryable=retryable)
            if outcome == "retry_wait":
                result.retry_wait += 1
            else:
                result.failed += 1
        finally:
            stop_heartbeat.set()
            thread.join(timeout=2)
    return result
