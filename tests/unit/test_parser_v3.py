import pytest

from ipoipo.sources.ipoipo_cn.parser import ParseError, parse_listing
from ipoipo.sources.ipoipo_cn.resolver import find_archive_url
from ipoipo.transport.http import FetchError, validate_url


REPORT_HTML = """
<div class="wapost card"><h2 class="multi-ellipsis">
<a href="https://ipoipo.cn/post/26028.html" title="报告 A">A</a>
</h2><span class="edit">2026-01-01</span></div>
"""


def test_report_parser():
    reports = parse_listing(REPORT_HTML, "85", "AI")
    assert len(reports) == 1
    assert reports[0].post_id == "26028"


def test_selector_drift_is_error():
    with pytest.raises(ParseError):
        parse_listing('<div class="wapost card"><h2>changed</h2></div>', "85", "AI")


def test_zip_url_query_and_allowlist():
    html = '<a href="https://ipo.ai-tag.cn/2026/x.ZIP?key=123">get</a>'
    assert find_archive_url(html, "https://ipoipo.cn/download/1.html",
                            ("ipoipo.cn", "ipo.ai-tag.cn")).endswith("?key=123")
    with pytest.raises(FetchError):
        find_archive_url('<a href="http://evil.example/x.zip">get</a>',
                         "https://ipoipo.cn/download/1.html", ("ipoipo.cn", "ipo.ai-tag.cn"))


@pytest.mark.parametrize("url", [
    "http://ipoipo.cn/x.zip",
    "https://127.0.0.1/private.zip",
    "https://evil.example/x.zip",
    "file:///etc/passwd",
    "https://user:pass@ipoipo.cn/x.zip",
])
def test_block_untrusted_urls(url):
    with pytest.raises(FetchError):
        validate_url(url, ("ipoipo.cn", "ipo.ai-tag.cn"))
