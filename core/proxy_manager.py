"""
代理管理器 - 解析Clash配置并管理代理节点
"""
import yaml
import time
import random
import socket
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from utils.logger import get_logger
from config.settings import CLASH_CONFIG_PATH, PROXY_TEST_TIMEOUT

logger = get_logger(__name__)


@dataclass
class ProxyNode:
    """代理节点"""
    name: str
    server: str
    port: int
    type: str
    password: str = ""
    cipher: str = ""
    uuid: str = ""
    alterId: int = 0
    latency: float = float('inf')
    fail_count: int = 0
    last_test_time: float = 0
    
    def to_requests_proxy(self, use_local_clash: bool = True, 
                          local_port: int = 7890) -> Dict[str, str]:
        """
        转换为requests库使用的代理格式
        
        Args:
            use_local_clash: 是否使用本地Clash代理（推荐）
            local_port: Clash本地代理端口
        """
        if use_local_clash:
            # 使用本地Clash代理端口（推荐方式）
            proxy_url = f"http://127.0.0.1:{local_port}"
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        
        # 直接连接模式（仅支持部分协议）
        if self.type in ["http", "https"]:
            proxy_url = f"{self.type}://{self.server}:{self.port}"
        elif self.type == "socks5":
            # 需要安装: pip install requests[socks]
            proxy_url = f"socks5://{self.server}:{self.port}"
        elif self.type in ["ss", "vmess"]:
            # Shadowsocks和VMess不能直接被requests使用
            # 必须通过本地客户端（如Clash）
            raise ValueError(
                f"协议 '{self.type}' 不支持直接连接，请使用 use_local_clash=True"
            )
        else:
            raise ValueError(f"不支持的代理类型: {self.type}")
        
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    def __repr__(self):
        return f"<ProxyNode {self.name} - {self.server}:{self.port} ({self.latency:.0f}ms)>"


class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config_path: str = None, use_local_clash: bool = True, 
                 local_port: int = 7890):
        """
        初始化代理管理器
        
        Args:
            config_path: Clash配置文件路径
            use_local_clash: 是否使用本地Clash代理（推荐True）
            local_port: Clash本地代理端口（默认7890）
        """
        self.config_path = config_path or CLASH_CONFIG_PATH
        self.use_local_clash = use_local_clash
        self.local_port = local_port
        self.nodes: List[ProxyNode] = []
        self.current_node: Optional[ProxyNode] = None
        self.load_config()
        
        if use_local_clash:
            logger.info(f"📡 使用本地Clash代理: http://127.0.0.1:{local_port}")
            logger.info("⚠️  请确保Clash客户端正在运行！")
    
    def load_config(self):
        """加载Clash配置文件"""
        try:
            logger.info(f"📂 加载代理配置: {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 解析代理节点
            proxies = config.get('proxies', [])
            for proxy in proxies:
                node = self._parse_proxy(proxy)
                if node:
                    self.nodes.append(node)
            
            # 尝试读取Clash的mixed-port配置
            if 'mixed-port' in config and self.use_local_clash:
                self.local_port = config['mixed-port']
                logger.info(f"📌 检测到Clash端口配置: {self.local_port}")
            
            logger.info(f"✅ 加载了 {len(self.nodes)} 个代理节点")
            
        except Exception as e:
            logger.error(f"❌ 加载配置失败: {e}")
            raise
    
    def _parse_proxy(self, proxy: Dict) -> Optional[ProxyNode]:
        """解析单个代理配置"""
        try:
            proxy_type = proxy.get('type', '').lower()
            
            if proxy_type == "ss":
                return ProxyNode(
                    name=proxy['name'],
                    server=proxy['server'],
                    port=proxy['port'],
                    type=proxy_type,
                    password=proxy.get('password', ''),
                    cipher=proxy.get('cipher', '')
                )
            elif proxy_type == "vmess":
                return ProxyNode(
                    name=proxy['name'],
                    server=proxy['server'],
                    port=proxy['port'],
                    type=proxy_type,
                    uuid=proxy.get('uuid', ''),
                    alterId=proxy.get('alterId', 0)
                )
            elif proxy_type in ["http", "https", "socks5"]:
                return ProxyNode(
                    name=proxy['name'],
                    server=proxy['server'],
                    port=proxy['port'],
                    type=proxy_type
                )
            else:
                logger.warning(f"⚠️ 不支持的代理类型: {proxy_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 解析代理失败: {e}")
            return None
    
    def test_node(self, node: ProxyNode, test_url: str = "www.google.com", 
                  test_port: int = 80) -> float:
        """测试单个节点延迟（TCP连接测试）"""
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(PROXY_TEST_TIMEOUT)
            sock.connect((node.server, node.port))
            latency = (time.time() - start) * 1000
            sock.close()
            
            node.latency = latency
            node.last_test_time = time.time()
            logger.debug(f"✅ {node.name}: {latency:.0f}ms")
            return latency
            
        except socket.timeout:
            node.latency = float('inf')
            node.fail_count += 1
            logger.warning(f"⏱️ {node.name}: 超时")
            return float('inf')
        except Exception as e:
            node.latency = float('inf')
            node.fail_count += 1
            logger.debug(f"❌ {node.name}: {e}")
            return float('inf')
    
    def test_all_nodes(self, max_workers: int = 10):
        """测试所有节点延迟"""
        logger.info(f"🔍 开始测试 {len(self.nodes)} 个节点...")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.test_node, node): node for node in self.nodes}
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"测试失败: {e}")
        
        # 按延迟排序
        self.nodes.sort(key=lambda n: n.latency)
        
        # 显示前10个最快的节点
        available = [n for n in self.nodes if n.latency < float('inf')]
        logger.info(f"✅ 可用节点: {len(available)}/{len(self.nodes)}")
        
        for i, node in enumerate(available[:10], 1):
            logger.info(f"  {i}. {node.name:40s} {node.latency:6.0f}ms")
    
    def select_fastest(self, region: Optional[str] = None) -> ProxyNode:
        """选择最快的节点"""
        nodes = self.nodes
        
        # 按地区筛选
        if region:
            nodes = [n for n in nodes if region.lower() in n.name.lower()]
            if not nodes:
                logger.warning(f"⚠️ 未找到地区 '{region}' 的节点，使用所有节点")
                nodes = self.nodes
        
        # 过滤掉失败次数过多的节点
        available = [n for n in nodes if n.latency < float('inf') and n.fail_count < 3]
        
        if not available:
            logger.warning("⚠️ 没有可用节点，尝试重新测试...")
            self.test_all_nodes()
            available = [n for n in nodes if n.latency < float('inf')]
        
        if not available:
            raise RuntimeError("❌ 没有可用的代理节点")
        
        # 选择延迟最低的
        fastest = min(available, key=lambda n: n.latency)
        self.current_node = fastest
        logger.info(f"🚀 选择节点: {fastest.name} ({fastest.latency:.0f}ms)")
        return fastest
    
    def select_random(self, max_latency: float = 500) -> ProxyNode:
        """随机选择一个低延迟节点"""
        available = [n for n in self.nodes if n.latency < max_latency and n.fail_count < 3]
        
        if not available:
            logger.warning("⚠️ 没有满足条件的节点，使用最快节点")
            return self.select_fastest()
        
        node = random.choice(available)
        self.current_node = node
        logger.info(f"🎲 随机选择: {node.name} ({node.latency:.0f}ms)")
        return node
    
    def get_proxy(self, strategy: str = "fastest", region: Optional[str] = None) -> Dict[str, str]:
        """
        获取代理（返回requests格式）
        
        Args:
            strategy: 选择策略 ("fastest" 或 "random")
            region: 地区筛选（可选）
            
        Returns:
            代理配置字典，格式: {"http": "...", "https": "..."}
        """
        if strategy == "fastest":
            node = self.select_fastest(region)
        elif strategy == "random":
            node = self.select_random()
        else:
            raise ValueError(f"未知策略: {strategy}")
        
        return node.to_requests_proxy(
            use_local_clash=self.use_local_clash,
            local_port=self.local_port
        )
    
    def get_local_proxy(self) -> Dict[str, str]:
        """直接获取本地Clash代理配置（不需要选择节点）"""
        proxy_url = f"http://127.0.0.1:{self.local_port}"
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    def mark_node_failed(self, node: ProxyNode):
        """标记节点失败"""
        node.fail_count += 1
        logger.warning(f"⚠️ 节点失败: {node.name} (失败次数: {node.fail_count})")
    
    def get_available_nodes(self, max_latency: float = 500) -> List[ProxyNode]:
        """获取所有可用节点"""
        return [n for n in self.nodes if n.latency < max_latency and n.fail_count < 3]


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("使用本地Clash代理模式（推荐）")
    print("=" * 60)
    
    manager = ProxyManager(use_local_clash=True)
    
    # 方式1: 直接使用本地代理（最简单）
    proxy = manager.get_local_proxy()
    print(f"\n本地代理配置: {proxy}")
    
    # 方式2: 测试节点后选择（用于了解节点状态）
    print("\n" + "=" * 60)
    print("测试节点延迟（可选）")
    print("=" * 60)
    manager.test_all_nodes()
    
    # 选择最快的香港节点
    proxy = manager.get_proxy(strategy="fastest", region="香港")
    print(f"\n使用代理: {proxy}")
    
    print("\n" + "=" * 60)
    print("⚠️  重要提示:")
    print("  1. 确保Clash客户端正在运行")
    print("  2. 在Clash中选择合适的节点")
    print("  3. requests会通过Clash的本地端口访问代理")
    print("=" * 60)