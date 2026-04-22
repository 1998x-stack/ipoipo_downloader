"""Proxy manager: Clash YAML parsing, node testing, auto-switch.

负责从 Clash 配置文件中解析 Shadowsocks 节点，测试节点延迟，
并在节点失败时自动切换。仅支持 SS 协议节点，vmess/trojan/hysteria 等
其他协议会被静默忽略。
"""

import socket
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml

from logger import get_logger


@dataclass
class ProxyNode:
    """表示一个代理节点的数据结构。

    Attributes:
        name: 节点名称，用于日志输出和调试。
        server: 节点服务器地址（域名或 IP）。
        port: 节点服务器端口。
        type: 代理协议类型，当前仅支持 "ss"（Shadowsocks）。
        latency: 节点延迟（毫秒），初始值为无穷大，测试后更新。
        fail_count: 连续失败次数，达到阈值后节点被视为不可用。
    """

    name: str
    server: str
    port: int
    type: str
    latency: float = field(default=float("inf"))
    fail_count: int = field(default=0)


class ProxyManager:
    """代理管理器，负责节点加载、延迟测试、随机选择和故障切换。

    代理选择策略：
    1. 从 Clash YAML 配置中仅加载 SS 类型节点（其他协议被忽略）。
    2. 通过 TCP 连通性测试（而非 HTTP 健康检查）测量节点延迟。
    3. 优先从延迟低于阈值的健康节点中随机选择，实现负载均衡。
    4. 若无健康节点，则回退到延迟最低的节点。
    5. 节点失败次数达到 3 次后自动标记为不可用。
    """

    def __init__(
        self,
        config_path: str,
        local_port: int = 7890,
        max_latency: int = 500,
    ) -> None:
        """初始化代理管理器。

        Args:
            config_path: Clash YAML 配置文件路径。
            local_port: Clash 本地监听端口，默认 7890。
            max_latency: 节点最大可接受延迟（毫秒），默认 500。
        """
        self.config_path: str = config_path
        self.local_port: int = local_port
        self.max_latency: int = max_latency
        self.nodes: List[ProxyNode] = []
        self.current_node: Optional[ProxyNode] = None
        self.log = get_logger("proxy")
        self._load_config()

    def _load_config(self) -> None:
        """加载并解析 Clash YAML 配置文件。

        仅提取 type 为 "ss" 的 Shadowsocks 节点。如果配置中包含
        mixed-port 字段，则自动更新 local_port。

        Raises:
            Exception: 配置文件读取或解析失败时抛出原始异常。
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as file_handle:
                config: Dict[str, object] = yaml.safe_load(file_handle)

            # 从配置中读取 mixed-port，覆盖默认端口
            if "mixed-port" in config:
                self.local_port = int(config["mixed-port"])

            # 仅筛选 SS 协议节点，vmess/trojan/hysteria 等会被忽略
            for proxy_entry in config.get("proxies", []):
                if proxy_entry.get("type") == "ss":
                    node = ProxyNode(
                        name=proxy_entry["name"],
                        server=proxy_entry["server"],
                        port=proxy_entry["port"],
                        type=proxy_entry["type"],
                    )
                    self.nodes.append(node)

            self.log.info(
                f"Loaded {len(self.nodes)} proxy nodes from {self.config_path}"
            )
        except Exception as exc:
            self.log.error(f"Failed to load proxy config: {exc}")
            raise

    def test_node(self, node: ProxyNode, timeout: float = 3.0) -> float:
        """使用 TCP 连接测试单个节点的延迟。

        采用 TCP connect 测试而非 HTTP 健康检查，因为：
        - TCP 连接测试更快，不需要等待 HTTP 响应。
        - 只需确认节点可达，不需要验证代理功能是否正常。

        Args:
            node: 要测试的代理节点。
            timeout: 连接超时时间（秒），必须大于 0。

        Returns:
            节点延迟（毫秒），连接失败时返回 float("inf")。
        """
        # 边界检查：超时时间必须为正数
        if timeout <= 0:
            node.latency = float("inf")
            node.fail_count += 1
            return float("inf")

        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((node.server, node.port))
            latency_ms = (time.time() - start_time) * 1000
            sock.close()
            node.latency = latency_ms
            return latency_ms
        except Exception:
            node.latency = float("inf")
            node.fail_count += 1
            return float("inf")

    def test_all_nodes(self, max_workers: int = 10) -> None:
        """并行测试所有节点的延迟。

        使用线程池并发测试节点，测试完成后按延迟升序排序。

        Args:
            max_workers: 最大并发线程数，默认 10。
        """
        # 边界检查：无节点时直接返回
        if not self.nodes:
            self.log.warn("No nodes to test")
            return

        self.log.info(f"Testing {len(self.nodes)} nodes...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.test_node, node): node
                for node in self.nodes
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    self.log.error(f"Node test failed: {exc}")

        # 按延迟升序排序
        self.nodes.sort(key=lambda node: node.latency)
        tested_nodes = [node for node in self.nodes if node.latency < float("inf")]
        self.log.info(f"Available nodes: {len(tested_nodes)}/{len(self.nodes)}")

    def select_random(self, max_latency: Optional[int] = None) -> ProxyNode:
        """从可用节点中随机选择一个。

        优先从延迟低于阈值且失败次数小于 3 的节点中随机选择，
        以实现负载均衡。若无符合条件的节点，则回退到最快节点。

        Args:
            max_latency: 最大可接受延迟（毫秒），默认使用实例的 max_latency。

        Returns:
            选中的代理节点。

        Raises:
            RuntimeError: 当没有任何可用节点时抛出。
        """
        threshold = max_latency or self.max_latency
        candidate_nodes = [
            node
            for node in self.nodes
            if node.latency < threshold and node.fail_count < 3
        ]

        # 无符合条件的节点时，回退到最快节点
        if not candidate_nodes:
            self.log.warn("No nodes meet latency threshold, selecting fastest")
            return self._select_fastest()

        node = random.choice(candidate_nodes)
        self.current_node = node
        self.log.info(f"Selected node: {node.name} ({node.latency:.0f}ms)")
        return node

    def _select_fastest(self) -> ProxyNode:
        """选择延迟最低的节点作为回退方案。

        优先从已测试过的节点中选择；若所有节点均未测试，则从全部节点中选择。

        Returns:
            延迟最低的代理节点。

        Raises:
            RuntimeError: 当节点列表为空时抛出。
        """
        tested_nodes = [
            node for node in self.nodes if node.latency < float("inf")
        ]
        candidate_nodes = tested_nodes if tested_nodes else self.nodes

        if not candidate_nodes:
            raise RuntimeError("No available proxy nodes")

        fastest_node = min(candidate_nodes, key=lambda node: node.latency)
        self.current_node = fastest_node
        self.log.info(
            f"Selected fastest node: {fastest_node.name} ({fastest_node.latency:.0f}ms)"
        )
        return fastest_node

    def get_local_proxy(self) -> Dict[str, str]:
        """获取本地代理地址字典，用于 requests.Session.proxies。

        Returns:
            包含 http 和 https 代理地址的字典，格式为
            {"http": "http://127.0.0.1:{port}", "https": "http://127.0.0.1:{port}"}。
        """
        return {
            "http": f"http://127.0.0.1:{self.local_port}",
            "https": f"http://127.0.0.1:{self.local_port}",
        }

    def mark_node_failed(self, node: ProxyNode) -> None:
        """标记节点为失败，增加其 fail_count 计数。

        当 fail_count 达到 3 时，该节点在 select_random 中会被自动排除。

        Args:
            node: 要标记为失败的代理节点。
        """
        node.fail_count += 1
        self.log.warn(
            f"Node failed: {node.name} (failures: {node.fail_count})"
        )

    def switch_node(self) -> bool:
        """切换到新的代理节点。

        先将当前节点标记为失败，然后调用 select_random 选择新节点。

        Returns:
            切换成功返回 True，无可用节点时返回 False。
        """
        if self.current_node is not None:
            self.mark_node_failed(self.current_node)
        try:
            self.select_random()
            return True
        except RuntimeError:
            self.log.error("No nodes available for switch")
            return False
