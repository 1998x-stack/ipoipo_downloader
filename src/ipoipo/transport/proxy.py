"""Explicit proxy endpoint configuration, without unverifiable node switching."""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProxyEndpoint:
    url: str

    def __post_init__(self) -> None:
        p = urlsplit(self.url)
        if p.scheme not in {"http", "https", "socks5", "socks5h"} or not p.hostname:
            raise ValueError("Invalid proxy endpoint")

    def for_requests(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}
