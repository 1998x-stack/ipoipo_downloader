"""Browser header generation with rotating User-Agents."""

from fake_headers import Headers

_fake = Headers(browser="chrome", os="mac")

# Full browser fingerprint headers (sec-ch-ua, Sec-Fetch-*, etc.)
# These are merged with fake-headers output to provide complete fingerprints
FINGERPRINT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def get_browser_headers(referer: str = None) -> dict:
    """Return rotating browser headers with full fingerprint.

    Each call generates a fresh User-Agent via fake-headers,
    merged with consistent Sec-Fetch-* and Accept headers.
    """
    headers = _fake.generate()
    headers.update(FINGERPRINT_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


def get_download_headers(referer: str) -> dict:
    """Return headers for ZIP download (must have Referer)."""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
