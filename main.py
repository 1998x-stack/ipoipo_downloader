"""
主程序 - IPO报告下载器
"""
import sys
import argparse
from utils.logger import get_logger
from core.proxy_manager import ProxyManager
from core.http_client import HTTPClient
from core.database import Database
from download.file_manager import FileManager
from scrapers.category_scraper import CategoryScraper
from scrapers.list_scraper import ListScraper
from scrapers.download_scraper import DownloadScraper
from download.downloader import Downloader
from config.settings import USE_PROXY

logger = get_logger(__name__)


class IPODownloader:
    """IPO报告下载器主类"""
    
    def __init__(self, use_proxy: bool = USE_PROXY):
        logger.info("🚀 初始化IPO报告下载器...")
        
        # 初始化代理管理器
        self.proxy_manager = None
        if use_proxy:
            try:
                self.proxy_manager = ProxyManager()
                logger.info("⏳ 测试代理节点...")
                self.proxy_manager.test_all_nodes()
            except Exception as e:
                logger.error(f"❌ 代理初始化失败: {e}")
                logger.warning("⚠️ 将不使用代理继续运行")
        
        # 初始化核心组件
        self.client = HTTPClient(
            use_proxy=use_proxy and self.proxy_manager is not None,
            proxy_manager=self.proxy_manager
        )
        self.db = Database()
        self.fm = FileManager()
        
        # 初始化爬虫
        self.category_scraper = CategoryScraper(self.client, self.db)
        self.list_scraper = ListScraper(self.client, self.db)
        self.download_scraper = DownloadScraper(self.client, self.db)
        self.downloader = Downloader(self.client, self.db, self.fm)
        
        logger.info("✅ 初始化完成！\n")
    
    def stage1_scrape_categories(self):
        """Stage 1: 爬取分类"""
        self.category_scraper.scrape_all_categories()
    
    def stage2_scrape_lists(self, max_pages: int = None, categories: list = None):
        """Stage 2: 爬取报告列表"""
        if categories:
            # 爬取指定分类
            for category_id in categories:
                category = self.db.get_all_categories()
                category = [c for c in category if c['category_id'] == category_id]
                if category:
                    self.list_scraper.scrape_category(
                        category[0]['category_id'],
                        category[0]['category_name'],
                        max_pages=max_pages
                    )
        else:
            # 爬取所有分类
            self.list_scraper.scrape_all_categories(max_pages_per_category=max_pages)
    
    def stage3_get_download_urls(self, limit: int = None):
        """Stage 3 & 4: 获取下载链接"""
        self.download_scraper.process_all_pending_reports(limit=limit or 100)
    
    def stage4_download_reports(self, max_reports: int = None, 
                               category: str = None,
                               force: bool = False,
                               concurrent: bool = False):
        """Stage 5: 下载报告"""
        if category:
            self.downloader.download_reports_by_category(
                category, 
                max_reports=max_reports,
                force=force
            )
        else:
            self.downloader.download_all_reports(
                max_reports=max_reports,
                force=force,
                use_concurrent=concurrent
            )
    
    def run_full_pipeline(self, max_pages: int = None, 
                          max_reports: int = None,
                          categories: list = None):
        """运行完整流程"""
        logger.info("=" * 60)
        logger.info("🚀 开始完整流程")
        logger.info("=" * 60)
        
        # Stage 1: 爬取分类
        self.stage1_scrape_categories()
        
        # Stage 2: 爬取报告列表
        self.stage2_scrape_lists(max_pages=max_pages, categories=categories)
        
        # Stage 3 & 4: 获取下载链接
        self.stage3_get_download_urls()
        
        # Stage 5: 下载报告
        self.stage4_download_reports(max_reports=max_reports)
        
        # 显示最终统计
        self.show_stats()
    
    def show_stats(self):
        """显示统计信息"""
        stats = self.db.get_stats()
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 统计信息")
        logger.info("=" * 60)
        logger.info(f"分类数量: {stats['total_categories']}")
        logger.info(f"报告总数: {stats['total_reports']}")
        logger.info(f"\n按状态分布:")
        for status, count in stats.get('reports_by_status', {}).items():
            logger.info(f"  - {status}: {count}")
        logger.info(f"\n下载统计:")
        logger.info(f"  - 已完成: {stats.get('downloads_completed', 0)}")
        logger.info(f"  - 失败: {stats.get('downloads_failed', 0)}")
        logger.info("=" * 60)
    
    def cleanup(self):
        """清理资源"""
        logger.info("🧹 清理资源...")
        self.client.close()
        self.db.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="IPO报告下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整流程（每个分类只爬前2页，最多下载10个报告）
  python main.py --full --max-pages 2 --max-reports 10
  
  # 只爬取分类
  python main.py --stage1
  
  # 只爬取报告列表（所有分类，每个5页）
  python main.py --stage2 --max-pages 5
  
  # 只获取下载链接（前50个）
  python main.py --stage3 --limit 50
  
  # 只下载报告（最多20个，使用并发）
  python main.py --stage4 --max-reports 20 --concurrent
  
  # 下载指定分类的报告
  python main.py --stage4 --category 34 --max-reports 10
  
  # 显示统计信息
  python main.py --stats
  
  # 不使用代理
  python main.py --full --no-proxy
        """
    )
    
    # 运行模式
    parser.add_argument('--full', action='store_true', 
                       help='运行完整流程（所有stage）')
    parser.add_argument('--stage1', action='store_true',
                       help='只运行Stage 1: 爬取分类')
    parser.add_argument('--stage2', action='store_true',
                       help='只运行Stage 2: 爬取报告列表')
    parser.add_argument('--stage3', action='store_true',
                       help='只运行Stage 3: 获取下载链接')
    parser.add_argument('--stage4', action='store_true',
                       help='只运行Stage 4: 下载报告')
    parser.add_argument('--stats', action='store_true',
                       help='显示统计信息')
    
    # 参数
    parser.add_argument('--max-pages', type=int,
                       help='每个分类最多爬取的页数')
    parser.add_argument('--max-reports', type=int,
                       help='最多下载的报告数')
    parser.add_argument('--limit', type=int,
                       help='处理的报告数限制')
    parser.add_argument('--category', type=str,
                       help='指定分类ID（例如: 34）')
    parser.add_argument('--categories', type=str, nargs='+',
                       help='指定多个分类ID（例如: 34 69 85）')
    
    # 选项
    parser.add_argument('--no-proxy', action='store_true',
                       help='不使用代理')
    parser.add_argument('--force', action='store_true',
                       help='强制重新下载已存在的文件')
    parser.add_argument('--concurrent', action='store_true',
                       help='使用并发下载')
    
    args = parser.parse_args()
    
    # 检查是否指定了操作
    if not any([args.full, args.stage1, args.stage2, args.stage3, args.stage4, args.stats]):
        parser.print_help()
        sys.exit(0)
    
    # 初始化下载器
    try:
        downloader = IPODownloader(use_proxy=not args.no_proxy)
        
        # 执行操作
        if args.stats:
            downloader.show_stats()
        
        if args.stage1:
            downloader.stage1_scrape_categories()
        
        if args.stage2:
            downloader.stage2_scrape_lists(
                max_pages=args.max_pages,
                categories=args.categories
            )
        
        if args.stage3:
            downloader.stage3_get_download_urls(limit=args.limit)
        
        if args.stage4:
            downloader.stage4_download_reports(
                max_reports=args.max_reports,
                category=args.category,
                force=args.force,
                concurrent=args.concurrent
            )
        
        if args.full:
            downloader.run_full_pipeline(
                max_pages=args.max_pages,
                max_reports=args.max_reports,
                categories=args.categories
            )
        
        # 显示最终统计
        if not args.stats:
            downloader.show_stats()
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断")
    except Exception as e:
        logger.error(f"\n❌ 发生错误: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            downloader.cleanup()
        except:
            pass
    
    logger.info("\n✅ 程序结束")


if __name__ == "__main__":
    main()