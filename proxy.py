"""Proxy manager: Clash YAML parsing, node testing, auto-switch."""
import yaml
import socket
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from dataclasses import dataclass
from logger import get_logger


@dataclass
class ProxyNode:
    name: str
    server: str
    port: int
    type: str
    latency: float = float("inf")
    fail_count: int = 0


class ProxyManager:
    def __init__(self, config_path: str, local_port: int = 7890, max_latency: int = 500):
        self.config_path = config_path
        self.local_port = local_port
        self.max_latency = max_latency
        self.nodes: List[ProxyNode] = []
        self.current_node: Optional[ProxyNode] = None
        self.log = get_logger("proxy")
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "mixed-port" in config:
                self.local_port = config["mixed-port"]
            for proxy in config.get("proxies", []):
                if proxy.get("type") == "ss":
                    node = ProxyNode(
                        name=proxy["name"],
                        server=proxy["server"],
                        port=proxy["port"],
                        type=proxy["type"],
                    )
                    self.nodes.append(node)
            self.log.info(f"Loaded {len(self.nodes)} proxy nodes from {self.config_path}")
        except Exception as e:
            self.log.error(f"Failed to load proxy config: {e}")
            raise

    def test_node(self, node: ProxyNode, timeout: float = 3.0) -> float:
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((node.server, node.port))
            latency = (time.time() - start) * 1000
            sock.close()
            node.latency = latency
            return latency
        except Exception:
            node.latency = float("inf")
            node.fail_count += 1
            return float("inf")

    def test_all_nodes(self, max_workers: int = 10):
        self.log.info(f"Testing {len(self.nodes)} nodes...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.test_node, n): n for n in self.nodes}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(f"Node test failed: {e}")
        self.nodes.sort(key=lambda n: n.latency)
        available = [n for n in self.nodes if n.latency < float("inf")]
        self.log.info(f"Available nodes: {len(available)}/{len(self.nodes)}")

    def select_random(self, max_latency: Optional[int] = None) -> ProxyNode:
        threshold = max_latency or self.max_latency
        available = [n for n in self.nodes if n.latency < threshold and n.fail_count < 3]
        if not available:
            self.log.warn("No nodes meet latency threshold, selecting fastest")
            return self._select_fastest()
        node = random.choice(available)
        self.current_node = node
        self.log.info(f"Selected node: {node.name} ({node.latency:.0f}ms)")
        return node

    def _select_fastest(self) -> ProxyNode:
        tested = [n for n in self.nodes if n.latency < float("inf")]
        pool = tested if tested else self.nodes
        if not pool:
            raise RuntimeError("No available proxy nodes")
        fastest = min(pool, key=lambda n: n.latency)
        self.current_node = fastest
        self.log.info(f"Selected fastest node: {fastest.name} ({fastest.latency:.0f}ms)")
        return fastest

    def get_local_proxy(self) -> Dict[str, str]:
        return {
            "http": f"http://127.0.0.1:{self.local_port}",
            "https": f"http://127.0.0.1:{self.local_port}",
        }

    def mark_node_failed(self, node: ProxyNode):
        node.fail_count += 1
        self.log.warn(f"Node failed: {node.name} (failures: {node.fail_count})")

    def switch_node(self) -> bool:
        if self.current_node:
            self.mark_node_failed(self.current_node)
        try:
            new_node = self.select_random()
            return True
        except RuntimeError:
            self.log.error("No nodes available for switch")
            return False
