"""Explicit proxy routing with optional loopback-only Clash controller and opt-in egress check.

Selecting a proxy node is never used to evade an origin site's HTTP 401/403/429.
"""
from dataclasses import dataclass
import ipaddress
from urllib.parse import quote, urlsplit

import requests


@dataclass(frozen=True)
class ProxyEndpoint:
    url: str

    def __post_init__(self) -> None:
        p = urlsplit(self.url)
        if p.scheme not in {"http", "https", "socks5", "socks5h"} or not p.hostname:
            raise ValueError("Invalid proxy endpoint")

    def for_requests(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}


class ProxyControlError(RuntimeError):
    """Proxy controller did not confirm the requested state."""


class ClashController:
    """Only operates a *local* authorized Clash/Mihomo controller.

    Verifies the controller-reported selected node. This is distinct from verifying
    the actual egress IP, which can be checked separately with an opt-in probe.
    """

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 5):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Proxy controller must be HTTP on loopback")
        if timeout <= 0:
            raise ValueError("Controller timeout must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def current_node(self, group: str) -> str:
        if not group or "/" in group or ".." in group:
            raise ValueError("Invalid proxy group")
        url = self.base_url + "/proxies/" + quote(group, safe="")
        try:
            response = self.session.get(
                url, headers=self.headers, timeout=self.timeout, allow_redirects=False
            )
            if response.status_code != 200:
                raise ProxyControlError(f"Proxy controller GET status {response.status_code}")
            payload = response.json()
            selected = payload.get("now")
            if not isinstance(selected, str) or not selected:
                raise ProxyControlError("Controller returned no selected node")
            return selected
        except (requests.RequestException, ValueError) as exc:
            raise ProxyControlError("Cannot read controller proxy group") from exc

    def select(self, group: str, node: str) -> str:
        if not node or ".." in node or "/" in node:
            raise ValueError("Invalid proxy node")
        # Validate the group before making any request.
        self.current_node(group)
        url = self.base_url + "/proxies/" + quote(group, safe="")
        try:
            response = self.session.put(
                url, json={"name": node}, headers=self.headers,
                timeout=self.timeout, allow_redirects=False
            )
            if response.status_code not in (200, 204):
                raise ProxyControlError(f"Proxy controller PUT status {response.status_code}")
        except requests.RequestException as exc:
            raise ProxyControlError("Cannot select proxy node") from exc
        observed = self.current_node(group)
        if observed != node:
            raise ProxyControlError("Controller did not confirm requested proxy node")
        return observed

    def close(self) -> None:
        self.session.close()


def observe_egress_ip(proxy: ProxyEndpoint, *, timeout: float = 8) -> str:
    """Opt-in HTTPS IP echo check routed via the configured proxy, never directly."""
    session = requests.Session()
    session.trust_env = False
    session.proxies.update(proxy.for_requests())
    try:
        response = session.get(
            "https://api.ipify.org?format=json", timeout=timeout, allow_redirects=False
        )
        if response.status_code != 200:
            raise ProxyControlError(f"Egress probe HTTP {response.status_code}")
        payload = response.json()
        address = payload.get("ip")
        if not isinstance(address, str):
            raise ProxyControlError("Egress probe did not return an IP")
        return str(ipaddress.ip_address(address))
    except (requests.RequestException, ValueError) as exc:
        raise ProxyControlError("Unable to validate proxy egress IP") from exc
    finally:
        session.close()
