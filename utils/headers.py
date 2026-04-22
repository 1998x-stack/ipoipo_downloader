"""Browser header generation with rotating User-Agents.

Generates randomized browser fingerprint headers to evade bot detection.
Each call produces a fresh User-Agent via the fake-headers library,
merged with consistent Sec-Fetch-* and Accept headers that mimic
real Chrome browser behavior.

完整浏览器指纹（含 sec-ch-ua、Sec-Fetch-* 等）可绕过大多数反爬检测，
因为服务端会校验这些头字段是否与实际浏览器一致。
"""

from typing import Optional

from fake_headers import Headers

# 模块级 fake-headers 实例，固定 Chrome/mac 指纹范围
_fake: Headers = Headers(browser="chrome", os="mac")

# 固定指纹头字段字典 —— 提供完整的浏览器特征标识
# 这些字段与 fake-headers 生成的 User-Agent 合并后，
# 形成与真实 Chrome 浏览器完全一致的请求头
FINGERPRINT_HEADERS: dict[str, str] = {
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


def get_browser_headers(referer: Optional[str] = None) -> dict[str, str]:
    """Return rotating browser headers with full fingerprint.

    Each call generates a fresh User-Agent via fake-headers,
    merged with consistent Sec-Fetch-* and Accept headers.

    每次调用都会生成全新的 User-Agent，配合固定的 Sec-Fetch-* 等字段，
    使请求看起来来自不同用户的真实浏览器，从而绕过基于指纹的反爬机制。

    Args:
        referer: Optional Referer URL. When provided, also sets
            Sec-Fetch-Site to "cross-site" to simulate a cross-origin navigation.
            Empty string is treated the same as None (no Referer added).

    Returns:
        A dict of HTTP header key-value pairs ready for use in requests.

    Examples:
        >>> headers = get_browser_headers()
        >>> "User-Agent" in headers
        True
        >>> headers = get_browser_headers("https://example.com")
        >>> headers["Referer"]
        'https://example.com'
    """
    headers: dict[str, str] = _fake.generate()
    headers.update(FINGERPRINT_HEADERS)
    # referer 为空字符串或 None 时均不添加 —— 保持与原始行为一致
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


def get_download_headers(referer: str) -> dict[str, str]:
    """Return minimal headers for ZIP download (must have Referer).

    ZIP 文件托管在 ipo.ai-tag.cn 上，受 Referer ACL 保护。
    必须携带来自 ipoipo.cn 的 Referer 才能通过 CDN 校验，
    否则返回 403 Forbidden。

    Args:
        referer: The Referer URL, typically
            ``https://ipoipo.cn/download/{post_id}.html``.
            Must be a non-empty string; no validation is performed here.

    Returns:
        A dict of HTTP header key-value pairs for the ZIP download request.

    Examples:
        >>> headers = get_download_headers("https://ipoipo.cn/download/123.html")
        >>> headers["Referer"]
        'https://ipoipo.cn/download/123.html'
    """
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
