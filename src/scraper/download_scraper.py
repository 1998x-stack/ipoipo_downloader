"""
下载页爬虫 - 修复版（正确处理Tengine CDN防盗链）

关键修复：
1. 使用HTTPClient的Session保持cookies
2. 正确设置Referer（必须是ipoipo.cn域名）
3. 先访问下载页面建立会话，再下载文件
"""
import re
import time
from typing import Optional, Dict, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from src.utils.logger import get_logger
from src.model.http_client import HTTPClient
from src.model.database import Database
from src.config.settings import DOWNLOAD_URL

logger = get_logger(__name__)


class DownloadScraper:
    """
    下载页爬虫 - 处理防盗链
    
    Tengine CDN 防盗链机制:
    - 使用Referer ACL白名单
    - 只允许来自 ipoipo.cn 域名的Referer
    - 直接请求ZIP URL会返回403
    
    解决方案:
    - 使用同一个Session保持cookies
    - 先访问下载页面（获取cookies）
    - 下载时设置Referer为下载页面URL
    """
    
    def __init__(self, http_client: HTTPClient, database: Database):
        self.client = http_client
        self.db = database
    
    def get_download_page_url(self, post_id: str) -> str:
        """Stage 3: 将post URL转换为download URL"""
        return DOWNLOAD_URL.format(post_id)
    
    def extract_zip_url(self, html: str, base_url: str = None) -> Optional[str]:
        """
        从HTML中提取ZIP下载链接
        
        支持多种匹配方式以提高成功率
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 方法1: 查找href包含.zip的链接
            zip_links = soup.find_all('a', href=re.compile(r'\.zip$', re.I))
            if zip_links:
                url = zip_links[0].get('href')
                logger.debug(f"✅ 找到ZIP链接 (方法1-href匹配): {url}")
                return urljoin(base_url, url) if base_url else url
            
            # 方法2: 查找特定样式的链接
            links = soup.find_all('a', style=re.compile(r'font-size.*color'))
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if '.zip' in href.lower() or '.zip' in text.lower():
                    logger.debug(f"✅ 找到ZIP链接 (方法2-样式匹配): {href}")
                    return urljoin(base_url, href) if base_url else href
            
            # 方法3: 查找所有a标签，筛选文本包含.zip的
            all_links = soup.find_all('a')
            for link in all_links:
                text = link.get_text(strip=True)
                if '.zip' in text.lower():
                    href = link.get('href', '')
                    if href:
                        logger.debug(f"✅ 找到ZIP链接 (方法3-文本匹配): {href}")
                        return urljoin(base_url, href) if base_url else href
            
            # 方法4: 正则匹配HTML中的ZIP URL
            zip_pattern = r'https?://[^\s<>"\']+\.zip'
            matches = re.findall(zip_pattern, html, re.I)
            if matches:
                logger.debug(f"✅ 找到ZIP链接 (方法4-正则匹配): {matches[0]}")
                return matches[0]
            
            logger.warning("⚠️ 未找到ZIP下载链接")
            return None
            
        except Exception as e:
            logger.error(f"❌ 提取ZIP链接失败: {e}")
            return None
    
    def visit_download_page(self, download_page_url: str) -> Tuple[bool, Optional[str]]:
        """
        访问下载页面
        
        这一步非常重要：
        1. 建立会话，获取必要的cookies
        2. HTTPClient的Session会自动保存cookies
        
        Returns:
            (success, html_content)
        """
        logger.info(f"📄 访问下载页面: {download_page_url}")
        
        try:
            response = self.client.get(
                download_page_url,
                timeout=30
            )
            
            # 打印获取到的cookies（调试用）
            cookies = self.client.get_cookies()
            if cookies:
                logger.debug(f"🍪 获取到的Cookies: {list(cookies.keys())}")
            
            return True, response.text
            
        except Exception as e:
            logger.error(f"❌ 访问下载页面失败: {e}")
            return False, None
    
    def get_zip_download_url(self, post_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取ZIP文件的下载链接
        
        Args:
            post_id: 文章ID
            
        Returns:
            (zip_url, download_page_url) - 同时返回referer用于后续下载
        """
        try:
            # 获取下载页URL
            download_page_url = self.get_download_page_url(post_id)
            
            # 访问下载页面（建立session，获取cookies）
            success, html = self.visit_download_page(download_page_url)
            if not success or not html:
                return None, None
            
            # 模拟人类行为：短暂延迟
            time.sleep(0.5)
            
            # 提取ZIP链接
            zip_url = self.extract_zip_url(html, base_url=download_page_url)
            
            if zip_url:
                logger.info(f"✅ 找到ZIP链接: {zip_url}")
                
                # 更新数据库
                self.db.update_report_download_url(post_id, zip_url)
                
                # 返回zip_url和referer（下载页面URL）
                return zip_url, download_page_url
            else:
                logger.warning(f"⚠️ 未找到ZIP链接: {post_id}")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ 获取ZIP链接失败: {post_id} - {e}")
            return None, None
    
    def download_zip_file(self, zip_url: str, referer_url: str, 
                         save_path: str) -> bool:
        """
        下载ZIP文件（使用HTTPClient的download_file方法）
        
        关键：referer_url 必须是 ipoipo.cn 域名的下载页面URL
        
        Args:
            zip_url: ZIP文件URL (如 https://ipo.ai-tag.cn/2025/04/xxx.zip)
            referer_url: 来源页面URL (如 https://ipoipo.cn/xiazai/123456/)
            save_path: 保存路径
        """
        logger.info(f"📥 开始下载ZIP文件")
        logger.info(f"   URL: {zip_url}")
        logger.info(f"   Referer: {referer_url}")
        logger.info(f"   保存路径: {save_path}")
        
        # 使用HTTPClient的下载方法（会携带Session中的cookies）
        return self.client.download_file(
            url=zip_url,
            save_path=save_path,
            referer=referer_url,  # 关键：Referer必须是ipoipo.cn域名
            timeout=300
        )
    
    def process_report(self, post_id: str, download_file: bool = False, 
                      save_path: str = None) -> Optional[str]:
        """
        处理单个报告：获取下载链接并可选下载文件
        
        Args:
            post_id: 文章ID
            download_file: 是否立即下载文件
            save_path: 文件保存路径
            
        Returns:
            zip_url 或 None
        """
        # 获取下载链接（同时会访问下载页面建立session）
        zip_url, download_page_url = self.get_zip_download_url(post_id)
        
        if not zip_url:
            return None
        
        # 如果需要下载文件
        if download_file and save_path:
            # 短暂延迟，模拟人类行为
            time.sleep(1)
            
            success = self.download_zip_file(zip_url, download_page_url, save_path)
            
            if not success:
                logger.warning("⚠️ 下载失败，但已获取到链接")
        
        return zip_url
    
    def process_all_pending_reports(self, limit: int = 100):
        """处理所有待获取下载链接的报告"""
        logger.info("=" * 60)
        logger.info("🔗 Stage 3 & 4: 获取所有报告的下载链接")
        logger.info("=" * 60)
        
        reports = self.db.get_pending_reports(limit=limit)
        logger.info(f"📊 待处理报告: {len(reports)} 个")
        
        success_count = 0
        fail_count = 0
        
        for i, report in enumerate(reports, 1):
            post_id = report['post_id']
            title = report['title']
            
            logger.info(f"\n[{i}/{len(reports)}] {title}")
            
            zip_url, _ = self.get_zip_download_url(post_id)
            
            if zip_url:
                success_count += 1
                self.db.update_report_status(post_id, 'ready')
            else:
                fail_count += 1
                self.db.update_report_status(post_id, 'failed')
            
            # 请求间隔，避免过快
            if i < len(reports):
                time.sleep(2)
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 处理完成！")
        logger.info(f"  - 成功: {success_count}")
        logger.info(f"  - 失败: {fail_count}")
        logger.info(f"{'=' * 60}")
    
    def test_download_with_referer(self, zip_url: str, referer_url: str) -> bool:
        """
        测试：使用Referer下载文件
        用于验证防盗链绕过是否成功
        """
        logger.info("=" * 60)
        logger.info("🧪 测试下载（带Referer）")
        logger.info("=" * 60)
        
        logger.info(f"ZIP URL: {zip_url}")
        logger.info(f"Referer: {referer_url}")
        
        try:
            # 先访问referer页面建立session
            logger.info("📄 先访问来源页面...")
            self.client.get(referer_url, timeout=10)
            time.sleep(1)
            
            # 使用HEAD请求测试（不下载完整文件）
            headers = {
                'Referer': referer_url,
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Dest': 'document',
            }
            
            response = self.client.head(zip_url, headers=headers, timeout=30)
            
            logger.info(f"\n响应状态: {response.status_code}")
            logger.info(f"响应头:")
            for key in ['Content-Type', 'Content-Length', 'X-Tengine-Error']:
                if key in response.headers:
                    logger.info(f"  {key}: {response.headers[key]}")
            
            if response.status_code == 200:
                logger.info("\n✅ 测试成功！可以下载")
                file_size = response.headers.get('Content-Length', 'unknown')
                logger.info(f"文件大小: {file_size} 字节")
                return True
            elif response.status_code == 403:
                logger.error("\n❌ 测试失败！403 Forbidden")
                tengine_error = response.headers.get('X-Tengine-Error', '')
                if tengine_error:
                    logger.error(f"   X-Tengine-Error: {tengine_error}")
                return False
            else:
                logger.warning(f"\n⚠️ 意外的状态码: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"\n❌ 请求失败: {e}")
            return False


if __name__ == "__main__":
    from src.model.proxy_manager import ProxyManager
    
    # 初始化
    pm = ProxyManager()
    pm.test_all_nodes()
    
    # 使用随机节点的代理URL
    pm.select_random()
    proxy_url = f"http://127.0.0.1:{pm.local_port}"
    
    client = HTTPClient(use_proxy=True, proxy_url=proxy_url)
    
    # 假设Database类存在
    # db = Database()
    # scraper = DownloadScraper(client, db)
    
    # 测试防盗链绕过
    print("\n" + "=" * 60)
    print("🧪 测试防盗链绕过")
    print("=" * 60)
    
    test_zip_url = "https://ipo.ai-tag.cn/2025/04/202504291200327477262.zip"
    test_referer = "https://ipoipo.cn/xiazai/123456/"
    
    # 测试1: 不带Referer（应该失败）
    print("\n测试1: 不带Referer")
    try:
        response = client.head(test_zip_url, timeout=10)
        print(f"状态码: {response.status_code}")
    except Exception as e:
        print(f"失败: {e}")
    
    # 测试2: 带Referer（应该成功）
    print("\n测试2: 带Referer")
    print("先访问来源页面...")
    try:
        client.get(test_referer, timeout=10)
        time.sleep(1)
        
        headers = {'Referer': test_referer, 'Sec-Fetch-Site': 'cross-site'}
        response = client.head(test_zip_url, headers=headers, timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ 成功绕过防盗链！")
    except Exception as e:
        print(f"失败: {e}")
    
    client.close()