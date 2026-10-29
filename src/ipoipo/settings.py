"""Validated application settings with no directory side effects at import time."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    min_delay_seconds: float = 1.0
    request_timeout: float = 30.0
    download_timeout: float = 120.0
    max_html_bytes: int = 5 * 1024 * 1024
    max_archive_bytes: int = 512 * 1024 * 1024
    max_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_member_bytes: int = 512 * 1024 * 1024
    max_archive_entries: int = 128
    max_redirects: int = 3
    max_attempts: int = 3
    lease_seconds: int = 900
    proxy_url: str | None = None
    proxy_controller_url: str | None = None
    proxy_group: str | None = None
    proxy_node: str | None = None
    proxy_controller_token: str | None = None
    check_proxy_egress: bool = False
    keep_zip: bool = False
    allowed_hosts: tuple[str, ...] = ("ipoipo.cn", "ipo.ai-tag.cn")

    def __post_init__(self) -> None:
        if (self.proxy_node or self.proxy_group) and not (
            self.proxy_url and self.proxy_controller_url and self.proxy_group and self.proxy_node
        ):
            raise ValueError("Proxy selection requires URL, controller URL, group and node")
        if self.check_proxy_egress and not self.proxy_url:
            raise ValueError("Egress check requires an explicit proxy URL")
        if self.min_delay_seconds < 0 or self.request_timeout <= 0 or self.download_timeout <= 0:
            raise ValueError("Invalid HTTP timing settings")
        if min(self.max_html_bytes, self.max_archive_bytes, self.max_uncompressed_bytes,
               self.max_member_bytes, self.max_archive_entries, self.max_attempts,
               self.lease_seconds) <= 0:
            raise ValueError("All security and retry bounds must be positive")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "pipeline.sqlite3"

    @property
    def download_dir(self) -> Path:
        return self.data_dir / "downloads-v3"
