"""Transactional task state machine."""
from enum import StrEnum


class Stage(StrEnum):
    RESOLVE = "resolve"
    DOWNLOAD = "download"


class Status(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL = frozenset({Status.SUCCEEDED, Status.FAILED})
ALLOWED = {
    Status.PENDING: {Status.RUNNING},
    Status.RETRY_WAIT: {Status.RUNNING},
    Status.RUNNING: {Status.SUCCEEDED, Status.RETRY_WAIT, Status.FAILED},
    Status.FAILED: {Status.PENDING},
    Status.SUCCEEDED: set(),
}


def ensure_transition(before: str, after: str) -> None:
    if Status(after) not in ALLOWED[Status(before)]:
        raise ValueError(f"Invalid task transition {before} -> {after}")
