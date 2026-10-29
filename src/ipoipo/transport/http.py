"""Strict HTTP transport with validated redirects, bounded HTML and explicit errors."""
from urllib.parse import urljoin, urlsplit
import requests

from ipoipo.settings import Settings
from ipoipo.transport.rate_limit import RateLimiter
from ipoipo.transport.proxy import ProxyEndpoint


class FetchError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def validate_url(url: str, allowed_hosts: tuple[str, ...]) -> str:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise FetchError("Blocked unsafe URL", retryable=False)
    if p.hostname.lower() not in allowed_hosts:
        raise FetchError("Blocked untrusted download host", retryable=False)
    return url


class HttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.trust_env = False
        if settings.proxy_url:
            self.session.proxies.update(ProxyEndpoint(settings.proxy_url).for_requests())
        self.limiter = RateLimiter(settings.min_delay_seconds)

    def get(self, url: str, *, referer: str | None = None, stream: bool = False,
            timeout: float | None = None) -> requests.Response:
        for _ in range(self.settings.max_redirects + 1):
            validate_url(url, self.settings.allowed_hosts)
            self.limiter.wait()
            try:
                headers = {"User-Agent": "ipoipo-downloader/3.0 (respectful research client)"}
                if referer:
                    validate_url(referer, self.settings.allowed_hosts)
                    headers["Referer"] = referer
                response = self.session.get(url, headers=headers, allow_redirects=False,
                                            stream=True, timeout=timeout or self.settings.request_timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                raise FetchError(f"Network error: {exc}", retryable=True) from exc
            except requests.RequestException as exc:
                raise FetchError(f"HTTP request error: {exc}", retryable=True) from exc
            if response.status_code in {301, 302, 303, 307, 308}:
                target = response.headers.get("Location")
                response.close()
                if not target:
                    raise FetchError("Redirect missing Location", retryable=False)
                url = urljoin(url, target)
                continue
            if response.status_code in (401, 403, 404, 410):
                code = response.status_code
                response.close()
                raise FetchError(f"HTTP {code}", retryable=False)
            if response.status_code == 429 or response.status_code >= 500:
                code = response.status_code
                response.close()
                raise FetchError(f"HTTP {code}", retryable=True)
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                response.close()
                raise FetchError(str(exc), retryable=False) from exc
            return response
        raise FetchError("Too many redirects", retryable=False)

    def get_html(self, url: str, *, referer: str | None = None) -> str:
        response = self.get(url, referer=referer)
        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "html" not in content_type and "text/plain" not in content_type:
                raise FetchError("Unexpected HTML response media type", retryable=False)
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > self.settings.max_html_bytes:
                    raise FetchError("HTML response too large", retryable=False)
            if not data:
                raise FetchError("Empty HTML response", retryable=True)
            response.encoding = response.apparent_encoding or "utf-8"
            return bytes(data).decode(response.encoding, errors="replace")
        except requests.RequestException as exc:
            raise FetchError(f"HTML transfer failure: {exc}") from exc
        finally:
            response.close()

    def close(self) -> None:
        self.session.close()
