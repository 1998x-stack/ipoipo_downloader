"""Typed records exchanged between pipeline layers."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Report:
    post_id: str
    title: str
    category_id: str
    category_name: str
    detail_url: str
    publish_date: str = ""
    thumbnail_url: str = ""
    description: str = ""
    view_count: int = 0


@dataclass(frozen=True)
class Task:
    id: int
    post_id: str
    stage: str
    attempts: int
    max_attempts: int
    owner: str


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str
    size: int
    media_type: str
