"""
下载页爬虫 - Stage 3 & 4: 获取下载链接（修复防盗链）
"""
import re
import time
from typing import Optional, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.logger import get_logger
from core.http_client import HTTPClient
from core.database import Database
from config.settings import DOWNLOAD_URL

logger = get_logger(__name__)


class DownloadScraper:
    """下载页爬虫"""
    
    def __init__(self, http_client: HTTPClient, database: Database):
        self.client = http_client
        self.db = database
    
    def get_download_page_url(self, post_id: str) -> str:
        """Stage 3: 将post URL转换为download URL"""
        return DOWNLOAD_URL.format(post_id)
    
    def extract_zip_url(self, html: str, base_url: str = None) -> Optional[str]:
        """从HTML中提取ZIP下载链接"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 方法1: 查找包含.zip的链接
            zip_links = soup.find_all('a', href=re.compile(r'\.zip$', re.I))
            if zip_links:
                url = zip_links[0].get('href')
                return urljoin(base_url, url) if base_url else url
            
            # 方法2: 查找特定样式的链接（根据你提供的HTML结构）
            # <a style="font-size: 12px; color: rgb(0, 102, 204);" href="...">xxx.zip</a>
            links = soup.find_all('a', style=re.compile(r'font-size.*color'))
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if '.zip' in href.lower() or '.zip' in text.lower():
                    return urljoin(base_url, href) if base_url else href
            
            # 方法3: 查找所有a标签，筛选文本包含.zip的
            all_links = soup.find_all('a')
            for link in all_links:
                text = link.get_text(strip=True)
                if '.zip' in text.lower():
                    href = link.get('href', '')
                    if href:
                        return urljoin(base_url, href) if base_url else href
            
            logger.warning("⚠️ 未找到ZIP下载链接")
            return None
            
        except Exception as e:
            logger.error(f"❌ 提取ZIP链接失败: {e}")
            return None
    
    def build_download_headers(self, referer_url: str, zip_url: str) -> Dict[str, str]:
        """
        构建绕过防盗链的请求头
        
        关键点：
        1. Referer必须是下载页面URL
        2. 完整的浏览器User-Agent
        3. 其他浏览器常见请求头
        """
        # 解析ZIP URL的域名
        parsed = urlparse(zip_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        
        headers = {
            # 最关键：Referer必须是下载页面
            'Referer': referer_url,
            
            # 浏览器标识
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # 接受的内容类型
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            
            # 连接控制
            'Connection': 'keep-alive',
            
            # 缓存控制
            'Cache-Control': 'max-age=0',
            
            # 升级不安全请求
            'Upgrade-Insecure-Requests': '1',
            
            # Sec-Fetch系列（模拟浏览器）
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            
            # 浏览器特征
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }
        
        return headers
    
    def download_zip_file(self, zip_url: str, referer_url: str, 
                         save_path: str, chunk_size: int = 8192) -> bool:
        """
        下载ZIP文件（绕过防盗链）
        
        Args:
            zip_url: ZIP文件URL
            referer_url: 来源页面URL（用于Referer）
            save_path: 保存路径
            chunk_size: 分块下载大小
        """
        try:
            # 构建请求头
            headers = self.build_download_headers(referer_url, zip_url)
            
            logger.info(f"📥 开始下载: {zip_url}")
            logger.debug(f"🔑 Referer: {referer_url}")
            
            # 发送请求（使用stream=True支持大文件）
            response = self.client.get(
                zip_url, 
                headers=headers,
                stream=True,
                timeout=300  # 5分钟超时
            )
            
            # 检查响应
            if response.status_code == 403:
                logger.error(f"❌ 403 Forbidden - 防盗链拦截")
                logger.error(f"   可能原因：")
                logger.error(f"   1. Referer不正确: {referer_url}")
                logger.error(f"   2. 需要Cookie验证")
                logger.error(f"   3. 需要先访问下载页面")
                return False
            
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            # 分块下载
            downloaded = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 显示进度
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (chunk_size * 100) == 0:  # 每800KB显示一次
                                logger.debug(f"   下载进度: {progress:.1f}% ({downloaded}/{total_size})")
            
            logger.info(f"✅ 下载完成: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def get_zip_download_url(self, post_id: str, visit_page_first: bool = True) -> Optional[str]:
        """
        Stage 4: 获取ZIP文件的实际下载链接
        
        Args:
            post_id: 文章ID
            visit_page_first: 是否先访问页面获取cookie（重要！）
        """
        try:
            # 获取下载页URL
            download_page_url = self.get_download_page_url(post_id)
            logger.info(f"🔗 下载页: {download_page_url}")
            
            # 重要：先访问下载页面，建立会话和cookie
            if visit_page_first:
                logger.debug("🌐 先访问下载页面（获取cookie）...")
                # 使用普通的浏览器请求头
                page_headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
                response = self.client.get(download_page_url, headers=page_headers)
                
                # 短暂延迟，模拟人类行为
                time.sleep(1)
            else:
                response = self.client.get(download_page_url)
            
            # 提取ZIP链接
            zip_url = self.extract_zip_url(response.text, base_url=download_page_url)
            
            if zip_url:
                logger.info(f"✅ 找到ZIP链接: {zip_url}")
                
                # 更新数据库，同时保存referer
                self.db.update_report_download_url(post_id, zip_url)
                # 注意：你可能需要在数据库中添加referer_url字段
                # self.db.update_report_referer(post_id, download_page_url)
                
                return zip_url
            else:
                logger.warning(f"⚠️ 未找到ZIP链接: {post_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取ZIP链接失败: {post_id} - {e}")
            return None
    
    def process_report(self, post_id: str, download_file: bool = False, 
                      save_path: str = None) -> Optional[str]:
        """
        处理单个报告：获取下载链接并可选下载文件
        
        Args:
            post_id: 文章ID
            download_file: 是否立即下载文件
            save_path: 文件保存路径
        """
        # 获取下载链接
        zip_url = self.get_zip_download_url(post_id, visit_page_first=True)
        
        if not zip_url:
            return None
        
        # 如果需要下载文件
        if download_file and save_path:
            download_page_url = self.get_download_page_url(post_id)
            success = self.download_zip_file(zip_url, download_page_url, save_path)
            
            if not success:
                logger.warning("⚠️ 下载失败，但已获取到链接")
        
        return zip_url
    
    def process_all_pending_reports(self, limit: int = 100):
        """处理所有待下载的报告"""
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
            
            zip_url = self.process_report(post_id)
            
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
    
    def test_download_with_referer(self, zip_url: str, referer_url: str):
        """
        测试：使用Referer下载文件
        用于验证防盗链绕过是否成功
        """
        logger.info("=" * 60)
        logger.info("🧪 测试下载（带Referer）")
        logger.info("=" * 60)
        
        headers = self.build_download_headers(referer_url, zip_url)
        
        logger.info(f"ZIP URL: {zip_url}")
        logger.info(f"Referer: {referer_url}")
        logger.info(f"\n请求头:")
        for key, value in headers.items():
            logger.info(f"  {key}: {value}")
        
        try:
            # 只请求头部，不下载完整文件
            response = self.client.head(zip_url, headers=headers, timeout=30)
            
            logger.info(f"\n响应状态: {response.status_code}")
            logger.info(f"响应头:")
            for key, value in response.headers.items():
                logger.info(f"  {key}: {value}")
            
            if response.status_code == 200:
                logger.info("\n✅ 成功！可以下载")
                file_size = response.headers.get('content-length', 'unknown')
                logger.info(f"文件大小: {file_size} 字节")
                return True
            else:
                logger.error(f"\n❌ 失败！状态码: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"\n❌ 请求失败: {e}")
            return False


if __name__ == "__main__":
    from core.proxy_manager import ProxyManager
    
    # 初始化
    pm = ProxyManager()
    pm.test_all_nodes()
    
    client = HTTPClient(use_proxy=True, proxy_manager=pm)
    db = Database()
    
    scraper = DownloadScraper(client, db)
    
    # 测试案例：你提供的链接
    print("\n" + "=" * 60)
    print("🧪 测试防盗链绕过")
    print("=" * 60)
    
    test_zip_url = "https://ipo.ai-tag.cn/2023/12/202312251405085991116.zip"
    test_referer = "https://ipoipo.cn/xiazai/123456/"  # 替换为实际的下载页URL
    
    # 测试1: 不带Referer（应该失败）
    print("\n测试1: 不带Referer")
    try:
        response = client.head(test_zip_url, timeout=10)
        print(f"状态码: {response.status_code}")
    except Exception as e:
        print(f"失败: {e}")
    
    # 测试2: 带Referer（应该成功）
    print("\n测试2: 带Referer")
    scraper.test_download_with_referer(test_zip_url, test_referer)
    
    # 测试3: 完整流程
    print("\n" + "=" * 60)
    print("🔄 测试完整下载流程")
    print("=" * 60)
    scraper.process_all_pending_reports(limit=3)
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n📊 统计:")
    print(f"  - 总报告数: {stats['total_reports']}")
    print(f"  - 按状态分布: {stats.get('reports_by_status', {})}")
    
    client.close()
    db.close()