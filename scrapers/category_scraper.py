"""
分类爬虫 - Stage 1: 获取所有分类信息
"""
from typing import List, Dict
from utils.logger import get_logger
from core.http_client import HTTPClient
from core.database import Database
from config.settings import CATEGORY_NAMES, CATEGORY_PAGE_URL

logger = get_logger(__name__)


class CategoryScraper:
    """分类爬虫"""
    
    def __init__(self, http_client: HTTPClient, database: Database):
        self.client = http_client
        self.db = database
    
    def scrape_all_categories(self) -> List[Dict]:
        """爬取所有分类"""
        logger.info("=" * 60)
        logger.info("📚 Stage 1: 爬取分类列表")
        logger.info("=" * 60)
        
        categories = []
        
        for category_id, category_name in CATEGORY_NAMES.items():
            url = CATEGORY_PAGE_URL.format(category_id)
            
            category_data = {
                'category_id': category_id,
                'category_name': category_name,
                'url': url
            }
            
            categories.append(category_data)
            
            # 保存到数据库
            self.db.insert_category(category_id, category_name, url)
            logger.info(f"✅ {category_name} ({category_id}): {url}")
        
        logger.info(f"\n✅ 完成！共 {len(categories)} 个分类")
        return categories
    
    def get_categories_from_db(self) -> List[Dict]:
        """从数据库获取分类"""
        return self.db.get_all_categories()


if __name__ == "__main__":
    from core.proxy_manager import ProxyManager
    
    # 初始化
    pm = ProxyManager()
    pm.test_all_nodes()
    
    client = HTTPClient(use_proxy=True, proxy_manager=pm)
    db = Database()
    
    scraper = CategoryScraper(client, db)
    
    # 爬取分类
    categories = scraper.scrape_all_categories()
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n📊 统计: {stats['total_categories']} 个分类")
    
    client.close()
    db.close()