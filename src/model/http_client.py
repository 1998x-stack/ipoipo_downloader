"""
HTTP客户端 - 支持Session保持和防盗链绕过
"""
import time
import requests
from typing import Dict, Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HTTPClient:
    """
    HTTP客户端 - 使用Session保持cookies和连接状态
    
    关键特性：
    1. 使用 requests.Session 保持 cookies（防盗链绕过的关键）
    2. 支持代理配置
    3. 自动重试机制
    4. 完整的浏览器请求头模拟
    """
    
    # 默认浏览器请求头
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    def __init__(self, use_proxy: bool = False, proxy_manager=None, 
                 proxy_url: str = None, timeout: int = 30, max_retries: int = 3):
        """
        初始化HTTP客户端
        
        Args:
            use_proxy: 是否使用代理
            proxy_manager: 代理管理器实例
            proxy_url: 直接指定代理URL（如 "http://127.0.0.1:7890"）
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 用于跟踪最后一次请求的状态码
        self._last_status_code = None
        
        # 创建 Session - 关键！保持cookies和连接状态
        self.session = requests.Session()
        
        # 设置默认请求头
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        # 配置代理
        if use_proxy:
            if proxy_url:
                # 直接使用指定的代理URL
                self.session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.info(f"📡 使用代理: {proxy_url}")
            elif proxy_manager:
                # 从代理管理器获取代理
                proxy = proxy_manager.get_local_proxy()
                self.session.proxies = proxy
                logger.info(f"📡 使用代理: {proxy}")
        
        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get(self, url: str, headers: Dict = None, **kwargs) -> requests.Response:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            headers: 额外的请求头（会与默认头合并）
            **kwargs: 其他requests参数
        """
        return self._request('GET', url, headers=headers, **kwargs)
    
    def head(self, url: str, headers: Dict = None, **kwargs) -> requests.Response:
        """发送HEAD请求"""
        return self._request('HEAD', url, headers=headers, **kwargs)
    
    def post(self, url: str, headers: Dict = None, **kwargs) -> requests.Response:
        """发送POST请求"""
        return self._request('POST', url, headers=headers, **kwargs)
    
    def _request(self, method: str, url: str, headers: Dict = None, 
                 **kwargs) -> requests.Response:
        """
        发送请求（带重试）
        
        Args:
            method: HTTP方法
            url: 请求URL
            headers: 额外请求头
            **kwargs: 其他参数
        """
        # 设置默认超时
        kwargs.setdefault('timeout', self.timeout)
        
        # 合并请求头
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)
        
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method, url, headers=request_headers, **kwargs
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if e.response else None
                
                if status_code == 403:
                    # 403错误不重试，直接返回让调用者处理
                    logger.warning(f"⚠️ 请求失败 (尝试 {attempt}/{self.max_retries}): "
                                 f"403 Client Error: Forbidden for url: {url}")
                    raise
                
                logger.warning(f"⚠️ 请求失败 (尝试 {attempt}/{self.max_retries}): {e}")
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"⚠️ 请求失败 (尝试 {attempt}/{self.max_retries}): {e}")
            
            # 重试前等待
            if attempt < self.max_retries:
                time.sleep(2 ** attempt)
        
        # 所有重试都失败
        logger.error(f"❌ 请求失败,已重试 {self.max_retries} 次: {url}")
        raise last_error or requests.exceptions.RequestException(f"请求失败: {url}")
    
    def download_file(self, url: str, save_path: str, referer: str = None,
                     chunk_size: int = 8192, timeout: int = 300) -> bool:
        """
        下载文件（支持防盗链绕过）
        
        Args:
            url: 文件URL
            save_path: 保存路径
            referer: Referer URL（防盗链关键！）
            chunk_size: 分块大小
            timeout: 下载超时
        
        Returns:
            是否下载成功
        """
        # 重置状态码
        self._last_status_code = None
        
        # 构建下载请求头
        headers = self._get_download_headers(referer)
        
        logger.info(f"📥 开始下载: {url}")
        if referer:
            logger.debug(f"🔗 Referer: {referer}")
        
        try:
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=timeout,
                allow_redirects=True
            )
            
            # 记录状态码（供外部检查）
            self._last_status_code = response.status_code
            
            # 检查403错误
            if response.status_code == 403:
                logger.error(f"❌ 403 Forbidden - 防盗链拦截!")
                tengine_error = response.headers.get('X-Tengine-Error', '')
                if tengine_error:
                    logger.error(f"   X-Tengine-Error: {tengine_error}")
                logger.error(f"   Referer: {referer}")
                return False
            
            response.raise_for_status()
            
            # 验证内容类型（防止返回HTML错误页面）
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type.lower() and url.endswith('.zip'):
                logger.error(f"❌ 返回的是HTML而不是ZIP文件，可能是防盗链拦截")
                self._last_status_code = 403  # 标记为403
                return False
            
            # 获取文件大小
            total_size = int(response.headers.get('Content-Length', 0))
            if total_size > 0:
                logger.info(f"📊 文件大小: {total_size / 1024 / 1024:.2f} MB")
            
            # 创建目录
            import os
            os.makedirs(os.path.dirname(save_path) or '.', exist_ok=True)
            
            # 分块下载
            downloaded = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 显示进度
                        if total_size > 0 and downloaded % (chunk_size * 100) == 0:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"   下载进度: {progress:.1f}%")
            
            logger.info(f"✅ 下载完成: {save_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 下载失败: {e}")
            return False
    
    def _get_download_headers(self, referer: str = None) -> Dict[str, str]:
        """
        获取下载请求头
        
        Args:
            referer: 来源页面URL（防盗链关键）
        """
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
        }
        
        if referer:
            headers['Referer'] = referer
            headers['Sec-Fetch-Site'] = 'cross-site'  # 跨域请求
        else:
            headers['Sec-Fetch-Site'] = 'none'
        
        return headers
    
    def get_cookies(self) -> Dict[str, str]:
        """获取当前session的cookies"""
        return dict(self.session.cookies)
    
    def get_last_status_code(self) -> Optional[int]:
        """获取最后一次请求的状态码"""
        return self._last_status_code
    
    def clear_cookies(self):
        """清除session的cookies"""
        self.session.cookies.clear()
    
    def close(self):
        """关闭session"""
        self.session.close()
        logger.debug("🔒 HTTP客户端已关闭")


if __name__ == "__main__":
    # 测试代码
    client = HTTPClient(use_proxy=False)
    
    try:
        # 测试普通请求
        response = client.get("https://httpbin.org/get")
        print(f"状态码: {response.status_code}")
        print(f"Cookies: {client.get_cookies()}")
    finally:
        client.close()