import pytest

from ipoipo.transport.proxy import ClashController, ProxyControlError, ProxyEndpoint, observe_egress_ip


class Response:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self.payload = payload or {}
    def json(self):
        return self.payload


def test_controller_selection_requires_confirmed_state():
    controller = ClashController("http://127.0.0.1:9090", token="test-token")
    selected = {"now": "DIRECT"}
    calls = []

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return Response(payload=selected)

    def put(url, **kwargs):
        calls.append(("PUT", url, kwargs))
        selected["now"] = kwargs["json"]["name"]
        return Response(204)

    controller.session.get = get
    controller.session.put = put
    try:
        assert controller.select("GLOBAL", "NODE_A") == "NODE_A"
        assert len(calls) == 3
        assert calls[1][2]["headers"]["Authorization"] == "Bearer test-token"
        assert calls[1][2]["allow_redirects"] is False
    finally:
        controller.close()


def test_controller_rejects_remote_and_unconfirmed_changes():
    with pytest.raises(ValueError, match="loopback"):
        ClashController("http://remote.example:9090")
    ctrl = ClashController("http://127.0.0.1:9090")
    ctrl.session.get = lambda *a, **k: Response(payload={"now":"DIRECT"})
    ctrl.session.put = lambda *a, **k: Response(204)
    try:
        with pytest.raises(ProxyControlError, match="confirm"):
            ctrl.select("GLOBAL", "NODE_A")
    finally:
        ctrl.close()


def test_egress_probe_uses_configured_proxy(monkeypatch):
    fake = type("SessionStub", (), {})()
    fake.trust_env = True
    fake.proxies = {}
    called = []
    def get(url, **kw):
        called.append((url, kw))
        return Response(payload={"ip": "203.0.113.10"})
    fake.get = get
    fake.close = lambda: None
    monkeypatch.setattr("ipoipo.transport.proxy.requests.Session", lambda: fake)
    ip = observe_egress_ip(ProxyEndpoint("http://127.0.0.1:7890"))
    assert ip == "203.0.113.10"
    assert fake.trust_env is False
    assert fake.proxies["https"] == "http://127.0.0.1:7890"
    assert called[0][0].startswith("https://")
