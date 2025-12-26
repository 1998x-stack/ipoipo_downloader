"""
HTTP客户端 - 带代理和fake-headers支持
"""
import time
import random
import requests
from typing import Optional, Dict
from fake_headers import Headers
from utils.logger import get_logger
from config.settings import (
    REQUEST_DELAY, MAX_RETRIES, RETRY_DELAY, 
    DOWNLOAD_TIMEOUT, USE_PROXY
)
from core.proxy_manager import ProxyManager

logger = get_logger(__name__)


class HTTPClient:
    """HTTP客户端（支持代理和fake-headers）"""
    
    def __init__(self, use_proxy: bool = USE_PROXY, proxy_manager: ProxyManager = None):
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.headers_generator = Headers(headers=True)
        
        # 默认headers
        self.default_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """生成随机headers"""
        try:
            fake_headers = self.headers_generator.generate()
            headers = {**self.default_headers, **fake_headers}
            return headers
        except Exception as e:
            logger.warning(f"⚠️ 生成fake-headers失败: {e}，使用默认headers")
            return self.default_headers
    
    def _get_proxy(self) -> Optional[Dict[str, str]]:
        """获取代理"""
        if not self.use_proxy or not self.proxy_manager:
            return None
        
        try:
            return self.proxy_manager.get_proxy(strategy="random")
        except Exception as e:
            logger.error(f"❌ 获取代理失败: {e}")
            return None
    
    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """带重试的请求"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # 添加随机延迟
                if attempt > 1:
                    delay = random.uniform(*REQUEST_DELAY)
                    logger.debug(f"⏳ 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                
                # 准备请求参数
                headers = kwargs.pop('headers', None) or self._get_headers()
                proxies = kwargs.pop('proxies', None) or self._get_proxy()
                timeout = kwargs.pop('timeout', DOWNLOAD_TIMEOUT)
                
                # 发送请求
                logger.debug(f"🌐 [{method.upper()}] {url} (尝试 {attempt}/{MAX_RETRIES})")
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    proxies=proxies,
                    timeout=timeout,
                    **kwargs
                )
                
                response.raise_for_status()
                logger.debug(f"✅ 请求成功: {url} (状态码: {response.status_code})")
                return response
                
            except requests.exceptions.ProxyError as e:
                logger.warning(f"⚠️ 代理错误 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if self.proxy_manager and self.proxy_manager.current_node:
                    self.proxy_manager.mark_node_failed(self.proxy_manager.current_node)
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏱️ 请求超时 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ 请求失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                
            # 重试前等待
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt
                logger.info(f"⏳ 等待 {wait_time}秒后重试...")
                time.sleep(wait_time)
        
        raise RuntimeError(f"❌ 请求失败，已重试 {MAX_RETRIES} 次: {url}")
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET请求"""
        return self._request_with_retry('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """POST请求"""
        return self._request_with_retry('POST', url, **kwargs)
    
    def download_file(self, url: str, save_path: str, resume: bool = True) -> bool:
        """下载文件（支持断点续传）"""
        from pathlib import Path
        import os
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否需要断点续传
        if resume and save_path.exists():
            existing_size = save_path.stat().st_size
            headers = {'Range': f'bytes={existing_size}-'}
            mode = 'ab'
            logger.info(f"📥 断点续传: {save_path.name} (已下载 {existing_size} 字节)")
        else:
            existing_size = 0
            headers = {}
            mode = 'wb'
            logger.info(f"📥 开始下载: {save_path.name}")
        
        try:
            # 添加自定义headers
            request_headers = self._get_headers()
            request_headers.update(headers)
            
            response = self._request_with_retry(
                'GET', 
                url, 
                headers=request_headers,
                stream=True
            )
            
            # 获取文件总大小
            total_size = int(response.headers.get('content-length', 0)) + existing_size
            
            # 检查是否支持断点续传
            if resume and existing_size > 0:
                if response.status_code != 206:
                    logger.warning("⚠️ 服务器不支持断点续传，重新下载")
                    existing_size = 0
                    mode = 'wb'
            
            # 下载文件
            from tqdm import tqdm
            
            with open(save_path, mode) as f:
                with tqdm(total=total_size, initial=existing_size, unit='B', unit_scale=True) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            logger.info(f"✅ 下载完成: {save_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            return False
    
    def close(self):
        """关闭session"""
        self.session.close()


if __name__ == "__main__":
    # 测试代码
    from core.proxy_manager import ProxyManager
    
    pm = ProxyManager()
    pm.test_all_nodes()
    
    client = HTTPClient(use_proxy=True, proxy_manager=pm)
    
    try:
        response = client.get("https://ipoipo.cn")
        print(f"✅ 状态码: {response.status_code}")
        print(f"✅ 内容长度: {len(response.text)}")
    finally:
        client.close()