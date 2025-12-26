"""
列表爬虫 - Stage 2: 爬取每个分类下的报告列表
"""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from utils.logger import get_logger
from core.http_client import HTTPClient
from core.database import Database
from config.settings import CATEGORY_PAGE_URL, CATEGORY_PAGE_PAGINATED

logger = get_logger(__name__)


class ListScraper:
    """列表页爬虫"""
    
    def __init__(self, http_client: HTTPClient, database: Database):
        self.client = http_client
        self.db = database
    
    def parse_report_card(self, card_element) -> Optional[Dict]:
        """解析单个报告卡片"""
        try:
            # 提取标题和链接
            h2 = card_element.find('h2', class_='multi-ellipsis')
            if not h2:
                return None
            
            link = h2.find('a')
            if not link:
                return None
            
            title = link.get('title', '').strip()
            detail_url = link.get('href', '').strip()
            
            # 提取post_id（从URL中）
            # 例如: https://ipoipo.cn/post/26028.html -> 26028
            match = re.search(r'/post/(\d+)\.html', detail_url)
            if not match:
                return None
            post_id = match.group(1)
            
            # 提取缩略图
            img = card_element.find('img', class_='img-cover')
            thumbnail_url = img.get('src', '') if img else ''
            
            # 提取简介
            text_p = card_element.find('p', class_='text')
            description = text_p.get_text(strip=True) if text_p else ''
            
            # 提取浏览量和发布日期
            count_div = card_element.find('div', class_='count')
            view_count = 0
            publish_date = ''
            
            if count_div:
                view_span = count_div.find('span', class_='view-num')
                if view_span:
                    view_text = view_span.get_text(strip=True)
                    match = re.search(r'\d+', view_text)
                    if match:
                        view_count = int(match.group())
                
                edit_span = count_div.find('span', class_='edit')
                if edit_span:
                    publish_date = edit_span.get_text(strip=True)
            
            return {
                'post_id': post_id,
                'title': title,
                'detail_url': detail_url,
                'thumbnail_url': thumbnail_url,
                'description': description,
                'view_count': view_count,
                'publish_date': publish_date
            }
            
        except Exception as e:
            logger.error(f"❌ 解析报告卡片失败: {e}")
            return None
    
    def scrape_page(self, url: str) -> List[Dict]:
        """爬取单个页面"""
        try:
            response = self.client.get(url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 查找所有报告卡片
            cards = soup.find_all('div', class_='wapost card')
            
            reports = []
            for card in cards:
                report = self.parse_report_card(card)
                if report:
                    reports.append(report)
            
            return reports
            
        except Exception as e:
            logger.error(f"❌ 爬取页面失败: {url} - {e}")
            return []
    
    def scrape_category(self, category_id: str, category_name: str, 
                        max_pages: int = None) -> List[Dict]:
        """爬取单个分类的所有报告"""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"📑 爬取分类: {category_name} ({category_id})")
        logger.info(f"{'=' * 60}")
        
        all_reports = []
        page = 1
        
        while True:
            # 构造URL
            if page == 1:
                url = CATEGORY_PAGE_URL.format(category_id)
            else:
                url = CATEGORY_PAGE_PAGINATED.format(category_id, page)
            
            logger.info(f"📄 爬取第 {page} 页: {url}")
            
            # 爬取页面
            reports = self.scrape_page(url)
            
            if not reports:
                logger.info(f"⚠️ 第 {page} 页没有数据，停止爬取")
                break
            
            # 保存到数据库
            for report in reports:
                self.db.insert_report(
                    category_id=category_id,
                    post_id=report['post_id'],
                    title=report['title'],
                    detail_url=report['detail_url'],
                    thumbnail_url=report['thumbnail_url'],
                    view_count=report['view_count'],
                    publish_date=report['publish_date']
                )
            
            all_reports.extend(reports)
            logger.info(f"✅ 第 {page} 页: 获取 {len(reports)} 个报告")
            
            # 检查是否达到最大页数
            if max_pages and page >= max_pages:
                logger.info(f"⚠️ 达到最大页数限制: {max_pages}")
                break
            
            page += 1
        
        logger.info(f"\n✅ 完成！{category_name} 共 {len(all_reports)} 个报告")
        return all_reports
    
    def scrape_all_categories(self, max_pages_per_category: int = None):
        """爬取所有分类"""
        logger.info("=" * 60)
        logger.info("📚 Stage 2: 爬取所有分类的报告列表")
        logger.info("=" * 60)
        
        # 从数据库获取分类
        categories = self.db.get_all_categories()
        
        total_reports = 0
        for i, category in enumerate(categories, 1):
            logger.info(f"\n进度: {i}/{len(categories)}")
            reports = self.scrape_category(
                category['category_id'],
                category['category_name'],
                max_pages=max_pages_per_category
            )
            total_reports += len(reports)
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 全部完成！共爬取 {total_reports} 个报告")
        logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    from core.proxy_manager import ProxyManager
    
    # 初始化
    pm = ProxyManager()
    pm.test_all_nodes()
    
    client = HTTPClient(use_proxy=True, proxy_manager=pm)
    db = Database()
    
    scraper = ListScraper(client, db)
    
    # 测试：只爬取第一个分类的前2页
    categories = db.get_all_categories()
    if categories:
        test_category = categories[0]
        scraper.scrape_category(
            test_category['category_id'],
            test_category['category_name'],
            max_pages=2
        )
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n📊 统计:")
    print(f"  - 分类数: {stats['total_categories']}")
    print(f"  - 报告数: {stats['total_reports']}")
    
    client.close()
    db.close()