"""Extract and validate first allowed ZIP link from a public download page."""
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

from ipoipo.sources.ipoipo_cn.categories import BASE_URL
from ipoipo.transport.http import FetchError, HttpClient, validate_url


def find_archive_url(html: str, base_url: str, allowed_hosts: tuple[str, ...]) -> str:
    soup = BeautifulSoup(html, "lxml")
    candidates = [link.get("href", "") for link in soup.select("a[href]")]
    candidates += re.findall(r'https?://[^\s<>"\x27]+?\.zip(?:\?[^\s<>"\x27]*)?', html, re.I)
    for raw in candidates:
        url = urljoin(base_url, raw.strip())
        p = urlsplit(url)
        if p.path.lower().endswith(".zip"):
            try:
                return validate_url(url, allowed_hosts)
            except FetchError:
                continue
    raise FetchError("No allowed ZIP download URL found", retryable=False)


class Resolver:
    def __init__(self, http: HttpClient):
        self.http = http

    def resolve(self, post_id: str) -> str:
        if not post_id.isdigit():
            raise ValueError("Invalid post_id")
        page_url = f"{BASE_URL}/download/{post_id}.html"
        html = self.http.get_html(page_url)
        return find_archive_url(html, page_url, self.http.settings.allowed_hosts)
