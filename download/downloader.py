"""
下载管理器 - 负责下载和管理下载任务
"""
import os
from pathlib import Path
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import get_logger
from core.http_client import HTTPClient
from core.database import Database
from download.file_manager import FileManager
from config.settings import MAX_CONCURRENT_DOWNLOADS

logger = get_logger(__name__)


class Downloader:
    """下载管理器"""
    
    def __init__(self, http_client: HTTPClient, database: Database, 
                 file_manager: FileManager):
        self.client = http_client
        self.db = database
        self.fm = file_manager
    
    def download_report(self, report: Dict, force: bool = False) -> bool:
        """下载单个报告"""
        post_id = report['post_id']
        title = report['title']
        category_id = report['category_id']
        download_url = report.get('download_url')
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"📥 下载报告: {title}")
        logger.info(f"{'=' * 60}")
        
        # 检查是否已下载
        if not force and self.db.is_downloaded(post_id):
            logger.info(f"⏭️ 已下载，跳过: {title}")
            return True
        
        # 检查下载链接
        if not download_url:
            logger.error(f"❌ 没有下载链接: {title}")
            self.db.update_report_status(post_id, 'no_download_url')
            return False
        
        try:
            # 提取文件名
            zip_filename = self._extract_filename(download_url, title)
            
            # 获取保存路径
            zip_path = self.fm.get_zip_path(category_id, title, zip_filename)
            
            # 检查文件是否已存在
            if zip_path.exists() and not force:
                file_size = self.fm.get_file_size(zip_path)
                logger.info(f"⏭️ 文件已存在: {zip_path.name} ({self.fm.format_size(file_size)})")
                
                # 更新数据库
                download_id = self.db.insert_download(post_id, download_url, zip_filename)
                self.db.update_download_status(
                    download_id, 'completed',
                    str(zip_path), file_size
                )
                self.db.update_report_status(post_id, 'downloaded')
                return True
            
            # 创建下载记录
            download_id = self.db.insert_download(post_id, download_url, zip_filename)
            
            # 下载文件
            logger.info(f"🔗 下载链接: {download_url}")
            logger.info(f"💾 保存路径: {zip_path}")
            
            success = self.client.download_file(
                download_url,
                str(zip_path),
                resume=True
            )
            
            if success:
                file_size = self.fm.get_file_size(zip_path)
                logger.info(f"✅ 下载成功: {self.fm.format_size(file_size)}")
                
                # 更新数据库
                self.db.update_download_status(
                    download_id, 'completed',
                    str(zip_path), file_size
                )
                self.db.update_report_status(post_id, 'downloaded')
                
                # 解压文件
                self._extract_report(download_id, zip_path, title)
                
                return True
            else:
                logger.error(f"❌ 下载失败: {title}")
                self.db.update_download_status(
                    download_id, 'failed',
                    error_message="下载失败"
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ 下载出错: {e}")
            try:
                self.db.update_download_status(
                    download_id, 'failed',
                    error_message=str(e)
                )
            except:
                pass
            return False
    
    def _extract_filename(self, url: str, title: str) -> str:
        """从URL或标题提取文件名"""
        # 先从URL尝试提取
        parts = url.split('/')
        if parts:
            filename = parts[-1]
            if '.zip' in filename.lower():
                return filename
        
        # 使用标题作为文件名
        return self.fm.sanitize_filename(title) + '.zip'
    
    def _extract_report(self, download_id: int, zip_path: Path, title: str):
        """解压报告"""
        try:
            logger.info(f"📦 开始解压...")
            
            # 解压到同一目录
            extract_dir = self.fm.extract_zip(zip_path)
            
            if extract_dir:
                # 统计解压的文件
                extracted_files = self.fm.get_extracted_files(extract_dir)
                
                logger.info(f"✅ 解压成功: {len(extracted_files)} 个文件")
                
                # 记录到数据库
                from core.database import Database
                self.db.conn.cursor().execute('''
                    INSERT INTO extractions (download_id, extract_path, files_count, status, extracted_at)
                    VALUES (?, ?, ?, 'completed', CURRENT_TIMESTAMP)
                ''', (download_id, str(extract_dir), len(extracted_files)))
                self.db.conn.commit()
                
                return True
            else:
                logger.error(f"❌ 解压失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 解压出错: {e}")
            return False
    
    def download_reports_by_category(self, category_id: str, 
                                     max_reports: int = None,
                                     force: bool = False):
        """下载指定分类的所有报告"""
        # 获取分类下的报告
        reports = self.db.get_reports_by_category(category_id, status='ready')
        
        if not reports:
            logger.warning(f"⚠️ 分类 {category_id} 没有准备好的报告")
            return
        
        if max_reports:
            reports = reports[:max_reports]
        
        logger.info(f"📊 待下载报告: {len(reports)} 个")
        
        # 下载报告
        success_count = 0
        fail_count = 0
        
        for i, report in enumerate(reports, 1):
            logger.info(f"\n进度: {i}/{len(reports)}")
            
            if self.download_report(report, force=force):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 下载完成！")
        logger.info(f"  - 成功: {success_count}")
        logger.info(f"  - 失败: {fail_count}")
        logger.info(f"{'=' * 60}")
    
    def download_all_reports(self, max_reports: int = None,
                            force: bool = False,
                            use_concurrent: bool = False):
        """下载所有准备好的报告"""
        # 获取所有准备好的报告
        reports = []
        categories = self.db.get_all_categories()
        
        for category in categories:
            category_reports = self.db.get_reports_by_category(
                category['category_id'], 
                status='ready'
            )
            reports.extend(category_reports)
        
        if not reports:
            logger.warning("⚠️ 没有准备好的报告")
            return
        
        if max_reports:
            reports = reports[:max_reports]
        
        logger.info(f"📊 待下载报告: {len(reports)} 个")
        
        if use_concurrent:
            self._download_concurrent(reports, force)
        else:
            self._download_sequential(reports, force)
    
    def _download_sequential(self, reports: list, force: bool):
        """顺序下载"""
        success_count = 0
        fail_count = 0
        
        for i, report in enumerate(reports, 1):
            logger.info(f"\n进度: {i}/{len(reports)}")
            
            if self.download_report(report, force=force):
                success_count += 1
            else:
                fail_count += 1
        
        self._print_summary(success_count, fail_count)
    
    def _download_concurrent(self, reports: list, force: bool):
        """并发下载"""
        success_count = 0
        fail_count = 0
        
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
            futures = {
                executor.submit(self.download_report, report, force): report 
                for report in reports
            }
            
            for i, future in enumerate(as_completed(futures), 1):
                logger.info(f"\n进度: {i}/{len(reports)}")
                
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"❌ 下载异常: {e}")
                    fail_count += 1
        
        self._print_summary(success_count, fail_count)
    
    def _print_summary(self, success: int, fail: int):
        """打印下载摘要"""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 下载完成！")
        logger.info(f"  - 成功: {success}")
        logger.info(f"  - 失败: {fail}")
        logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    from core.proxy_manager import ProxyManager
    
    # 初始化
    pm = ProxyManager()
    pm.test_all_nodes()
    
    client = HTTPClient(use_proxy=True, proxy_manager=pm)
    db = Database()
    fm = FileManager()
    
    downloader = Downloader(client, db, fm)
    
    # 测试：下载前5个报告
    downloader.download_all_reports(max_reports=5)
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n📊 统计:")
    print(f"  - 下载完成: {stats.get('downloads_completed', 0)}")
    print(f"  - 下载失败: {stats.get('downloads_failed', 0)}")
    
    client.close()
    db.close()