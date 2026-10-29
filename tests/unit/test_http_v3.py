import pytest
from ipoipo.settings import Settings
from ipoipo.transport.http import FetchError, HttpClient


class FakeHTTPResponse:
    def __init__(self, code, location=None):
        self.status_code = code
        self.headers = {"Location": location} if location else {}
        self.closed = False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("Should classify first")


def test_redirect_target_is_validated_before_request(tmp_path):
    client = HttpClient(Settings(data_dir=tmp_path, min_delay_seconds=0))
    calls = []
    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeHTTPResponse(302, "https://localhost/blocked.zip")
    client.session.get = fake_get
    try:
        with pytest.raises(FetchError, match="Blocked"):
            client.get("https://ipoipo.cn/download/1.html")
        assert len(calls) == 1
    finally:
        client.close()


def test_forbidden_is_permanent(tmp_path):
    client = HttpClient(Settings(data_dir=tmp_path, min_delay_seconds=0))
    client.session.get = lambda url, **kwargs: FakeHTTPResponse(403)
    try:
        with pytest.raises(FetchError) as error:
            client.get("https://ipoipo.cn/download/1.html")
        assert error.value.retryable is False
    finally:
        client.close()
