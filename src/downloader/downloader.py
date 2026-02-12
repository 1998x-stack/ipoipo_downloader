"""
下载器 - 负责实际下载报告文件（完整版）

功能：
1. 下载 ZIP 文件（绕过防盗链）
2. 自动解压 ZIP 文件
3. 自动重命名文档（时间戳 + 报告标题）
4. 支持批量下载和重试
"""
import os
import time
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from src.utils.logger import get_logger
from src.model.http_client import HTTPClient
from src.model.database import Database
from src.downloader.file_manager import FileManager
from src.config.settings import DOWNLOAD_URL

logger = get_logger(__name__)


class Downloader:
    """
    报告下载器
    
    完整流程：
    1. 获取待下载报告信息
    2. 访问下载页面（建立session，获取cookies）
    3. 下载 ZIP 文件（使用正确的 Referer 绕过防盗链）
    4. 解压 ZIP 文件
    5. 重命名文档文件（时间戳 + 报告标题）
    6. 可选：删除原始 ZIP 文件
    """
    
    def __init__(self, http_client: HTTPClient, database: Database, 
                 file_manager: FileManager, 
                 auto_extract: bool = True,
                 auto_rename: bool = True,
                 keep_zip: bool = False,
                 proxy_switch_callback=None):
        """
        初始化下载器
        
        Args:
            http_client: HTTP客户端
            database: 数据库实例
            file_manager: 文件管理器
            auto_extract: 是否自动解压
            auto_rename: 是否自动重命名文档
            keep_zip: 是否保留ZIP文件
            proxy_switch_callback: 代理切换回调函数（403时自动调用）
        """
        self.client = http_client
        self.db = database
        self.fm = file_manager
        self.auto_extract = auto_extract
        self.auto_rename = auto_rename
        self.keep_zip = keep_zip
        self.proxy_switch_callback = proxy_switch_callback
        
        # 连续失败计数（用于触发代理切换）
        self._consecutive_failures = 0
        self._max_failures_before_switch = 2  # 连续失败2次后切换代理
    
    def get_download_page_url(self, post_id: str) -> str:
        """获取下载页面URL（用作Referer）"""
        return DOWNLOAD_URL.format(post_id)
    
    def _try_switch_proxy(self, reason: str = "download failed") -> bool:
        """
        尝试切换代理节点
        
        Args:
            reason: 切换原因
            
        Returns:
            是否成功切换
        """
        if self.proxy_switch_callback:
            logger.warning(f"⚠️ {reason}，尝试切换代理节点...")
            if self.proxy_switch_callback():
                self._consecutive_failures = 0
                time.sleep(2)  # 切换后等待一下
                return True
        return False
    
    def _handle_download_failure(self, is_403: bool = False) -> bool:
        """
        处理下载失败
        
        Args:
            is_403: 是否为403错误
            
        Returns:
            是否应该重试
        """
        self._consecutive_failures += 1
        
        # 403错误立即尝试切换代理
        if is_403:
            logger.error("❌ 403 Forbidden - 防盗链拦截")
            return self._try_switch_proxy("遭遇403防盗链拦截")
        
        # 连续失败多次后切换代理
        if self._consecutive_failures >= self._max_failures_before_switch:
            return self._try_switch_proxy(f"连续失败{self._consecutive_failures}次")
        
        return False
    
    def _reset_failure_count(self):
        """重置失败计数"""
        self._consecutive_failures = 0
    
    def download_report(self, report: Dict, force: bool = False, 
                       retry_on_403: bool = True) -> bool:
        """
        下载单个报告（完整流程：下载 -> 解压 -> 重命名）
        
        Args:
            report: 报告信息字典，包含:
                - post_id: 文章ID
                - title: 报告标题
                - download_url: ZIP下载链接
                - category_name: 分类名称
            force: 是否强制重新下载
            retry_on_403: 遇到403时是否切换代理重试
            
        Returns:
            是否成功
        """
        post_id = report['post_id']
        title = report['title']
        zip_url = report.get('download_url')
        category_name = report.get('category_name', 'unknown')
        
        logger.info(f"\n{'=' * 50}")
        logger.info(f"📄 处理报告: {title}")
        logger.info(f"{'=' * 50}")
        
        # 检查ZIP URL是否存在
        if not zip_url:
            logger.warning(f"⚠️ 没有下载链接: {post_id}")
            return False
        
        # 生成保存路径
        zip_filename = self._extract_filename_from_url(zip_url)
        save_path = self.fm.get_report_path(category_name, zip_filename)
        save_path_obj = Path(save_path)
        
        logger.info(f"📂 分类: {category_name}")
        logger.info(f"📁 保存路径: {save_path}")
        
        # 检查文件是否已存在
        if not force and save_path_obj.exists():
            file_size = save_path_obj.stat().st_size
            if file_size > 1024:  # 大于1KB认为是有效文件
                logger.info(f"⏭️ ZIP文件已存在，跳过下载")
                
                # 如果需要解压但还没解压，执行解压
                if self.auto_extract:
                    self._extract_and_rename(save_path_obj, title)
                
                self._reset_failure_count()
                return True
        
        # 构建下载页面URL（用作Referer）
        download_page_url = self.get_download_page_url(post_id)
        
        # 最多重试次数（包括切换代理后的重试）
        max_attempts = 3 if retry_on_403 else 1
        
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt > 1:
                    logger.info(f"🔄 第 {attempt} 次尝试...")
                
                # Step 1: 访问下载页面（建立session，获取cookies）
                logger.info(f"📄 Step 1: 访问下载页面...")
                logger.debug(f"   URL: {download_page_url}")
                self.client.get(download_page_url, timeout=30)
                
                # 短暂延迟，模拟人类行为
                time.sleep(1)
                
                # Step 2: 下载ZIP文件（使用下载页面URL作为Referer）
                logger.info(f"📥 Step 2: 下载ZIP文件...")
                logger.debug(f"   URL: {zip_url}")
                logger.debug(f"   Referer: {download_page_url}")
                
                # 确保目录存在
                self.fm.ensure_directory(save_path)
                
                success = self.client.download_file(
                    url=zip_url,
                    save_path=save_path,
                    referer=download_page_url,  # 关键：Referer必须是ipoipo.cn域名
                    timeout=300
                )
                
                if not success:
                    # 检查是否为403错误（需要从HTTPClient获取）
                    is_403 = getattr(self.client, '_last_status_code', None) == 403
                    
                    if is_403 and attempt < max_attempts:
                        if self._handle_download_failure(is_403=True):
                            continue  # 切换代理成功，重试
                    
                    self._handle_download_failure(is_403=False)
                    self.db.update_report_status(post_id, 'failed')
                    logger.error(f"❌ 下载失败: {title}")
                    return False
                
                # 验证下载的文件
                if not save_path_obj.exists() or save_path_obj.stat().st_size < 1024:
                    logger.error(f"❌ 下载的文件无效或太小")
                    
                    if attempt < max_attempts:
                        if self._handle_download_failure(is_403=False):
                            continue
                    
                    self.db.update_report_status(post_id, 'failed')
                    return False
                
                file_size = self.fm.format_size(save_path_obj.stat().st_size)
                logger.info(f"✅ 下载完成: {zip_filename} ({file_size})")
                
                # Step 3: 解压和重命名
                if self.auto_extract:
                    extract_success = self._extract_and_rename(save_path_obj, title)
                    if not extract_success:
                        logger.warning(f"⚠️ 解压失败，但ZIP文件已保存")
                
                # 更新数据库状态
                self.db.update_report_status(post_id, 'downloaded')
                self.db.update_report_local_path(post_id, save_path)
                
                # 重置失败计数
                self._reset_failure_count()
                
                logger.info(f"✅ 处理完成: {title}")
                return True
                    
            except Exception as e:
                logger.error(f"❌ 处理失败: {title} - {e}")
                import traceback
                logger.debug(traceback.format_exc())
                
                # 尝试切换代理重试
                if attempt < max_attempts:
                    if self._handle_download_failure(is_403=False):
                        continue
        
        # 所有尝试都失败
        self.db.update_report_status(post_id, 'failed')
        return False
    
    def _extract_filename_from_url(self, url: str) -> str:
        """从URL中提取文件名"""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        
        if filename.endswith('.zip'):
            return filename
        
        # 如果URL中没有有效文件名，生成一个
        return f"report_{int(time.time())}.zip"
    
    def _extract_and_rename(self, zip_path: Path, report_title: str) -> bool:
        """
        解压ZIP文件并重命名文档
        
        Args:
            zip_path: ZIP文件路径
            report_title: 报告标题（用于重命名）
            
        Returns:
            是否成功
        """
        logger.info(f"📦 Step 3: 解压和重命名...")
        
        try:
            # 验证ZIP文件
            if not self.fm.validate_and_fix_zip(zip_path):
                logger.error(f"❌ ZIP文件无效，跳过解压")
                return False
            
            # 解压到同一目录
            extract_dir = zip_path.parent
            
            # 调用FileManager的extract_zip方法
            # 这会自动：
            # 1. 从ZIP文件名提取时间戳
            # 2. 解压所有文件
            # 3. 重命名文档文件（时间戳 + 报告标题）
            result = self.fm.extract_zip(
                zip_path=zip_path,
                extract_to=extract_dir,
                report_title=report_title,
                auto_rename=self.auto_rename
            )
            
            if result is None:
                logger.error(f"❌ 解压失败")
                return False
            
            # 获取解压后的文档文件
            doc_files = self.fm.get_extracted_files(
                extract_dir, 
                extensions=self.fm.DOCUMENT_EXTENSIONS
            )
            
            if doc_files:
                logger.info(f"📋 解压后的文档文件:")
                for doc in doc_files:
                    size = self.fm.format_size(doc.stat().st_size)
                    logger.info(f"   - {doc.name} ({size})")
            
            # 清理ZIP文件（可选）
            if not self.keep_zip:
                self.fm.cleanup_zip(zip_path, keep_zip=False)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 解压过程出错: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def download_reports_by_category(self, category_id: str, 
                                     max_reports: int = None,
                                     force: bool = False) -> Dict[str, int]:
        """
        下载指定分类的报告
        
        Args:
            category_id: 分类ID
            max_reports: 最大下载数量
            force: 强制重新下载
            
        Returns:
            统计信息 {success: int, failed: int, skipped: int}
        """
        logger.info("=" * 60)
        logger.info(f"📂 开始下载分类 {category_id} 的报告")
        logger.info("=" * 60)
        
        # 获取待下载报告
        reports = self.db.get_reports_by_category(category_id, status='ready')
        
        if max_reports:
            reports = reports[:max_reports]
        
        logger.info(f"📊 待下载报告: {len(reports)} 个")
        
        if not reports:
            logger.info("✅ 没有待下载的报告")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        return self._download_sequential(reports, force)
    
    def download_all_reports(self, max_reports: int = None, 
                            force: bool = False,
                            use_concurrent: bool = False,
                            max_workers: int = 3) -> Dict[str, int]:
        """
        下载所有待下载的报告
        
        Args:
            max_reports: 最大下载数量
            force: 强制重新下载
            use_concurrent: 是否使用并发下载
            max_workers: 并发数量
            
        Returns:
            统计信息
        """
        logger.info("=" * 60)
        logger.info("📥 开始下载所有报告")
        logger.info("=" * 60)
        
        # 获取所有ready状态的报告
        reports = self.db.get_ready_reports(limit=max_reports or 1000)
        logger.info(f"📊 待下载报告: {len(reports)} 个")
        
        if not reports:
            logger.info("✅ 没有待下载的报告")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        if use_concurrent:
            return self._download_concurrent(reports, force, max_workers)
        else:
            return self._download_sequential(reports, force)
    
    def _download_sequential(self, reports: List[Dict], 
                            force: bool = False) -> Dict[str, int]:
        """顺序下载"""
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        total = len(reports)
        
        for i, report in enumerate(reports, 1):
            logger.info(f"\n[{i}/{total}] 开始处理...")
            
            try:
                success = self.download_report(report, force=force)
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                logger.error(f"❌ 处理异常: {e}")
                stats['failed'] += 1
            
            # 下载间隔（重要：避免触发防护）
            if i < total:
                logger.info("⏳ 等待2秒后继续...")
                time.sleep(2)
        
        self._print_stats(stats)
        return stats
    
    def _download_concurrent(self, reports: List[Dict], 
                            force: bool = False,
                            max_workers: int = 3) -> Dict[str, int]:
        """
        并发下载
        
        注意：并发下载时可能触发更多防护，建议谨慎使用
        """
        logger.warning("⚠️ 并发下载可能触发防盗链，如失败请改用顺序下载")
        
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_report = {
                executor.submit(self.download_report, report, force): report 
                for report in reports
            }
            
            for future in as_completed(future_to_report):
                report = future_to_report[future]
                try:
                    success = future.result()
                    if success:
                        stats['success'] += 1
                    else:
                        stats['failed'] += 1
                except Exception as e:
                    logger.error(f"❌ 下载异常: {report['title']} - {e}")
                    stats['failed'] += 1
        
        self._print_stats(stats)
        return stats
    
    def _print_stats(self, stats: Dict[str, int]):
        """打印统计信息"""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"📊 下载统计")
        logger.info(f"  - 成功: {stats['success']}")
        logger.info(f"  - 失败: {stats['failed']}")
        logger.info(f"  - 跳过: {stats['skipped']}")
        total = stats['success'] + stats['failed'] + stats['skipped']
        if total > 0:
            success_rate = (stats['success'] / total) * 100
            logger.info(f"  - 成功率: {success_rate:.1f}%")
        logger.info(f"{'=' * 60}")
    
    def retry_failed_downloads(self, max_reports: int = None) -> Dict[str, int]:
        """重试失败的下载"""
        logger.info("=" * 60)
        logger.info("🔄 重试失败的下载")
        logger.info("=" * 60)
        
        # 获取失败的报告
        reports = self.db.get_failed_reports(limit=max_reports or 100)
        logger.info(f"📊 待重试报告: {len(reports)} 个")
        
        if not reports:
            logger.info("✅ 没有失败的下载需要重试")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        # 重置状态为ready
        for report in reports:
            self.db.update_report_status(report['post_id'], 'ready')
        
        # 重新下载（强制模式）
        return self._download_sequential(reports, force=True)
    
    def extract_downloaded_zips(self, category_name: str = None, 
                               max_files: int = None) -> Dict[str, int]:
        """
        解压已下载但未解压的ZIP文件
        
        Args:
            category_name: 分类名称（可选，不指定则处理所有）
            max_files: 最大处理数量
            
        Returns:
            统计信息
        """
        logger.info("=" * 60)
        logger.info("📦 解压已下载的ZIP文件")
        logger.info("=" * 60)
        
        # 获取已下载的报告
        reports = self.db.get_downloaded_reports(limit=max_files or 1000)
        
        if category_name:
            reports = [r for r in reports if r.get('category_name') == category_name]
        
        logger.info(f"📊 待处理报告: {len(reports)} 个")
        
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for i, report in enumerate(reports, 1):
            title = report['title']
            local_path = report.get('local_path')
            
            if not local_path:
                logger.warning(f"⚠️ [{i}] 没有本地路径: {title}")
                stats['skipped'] += 1
                continue
            
            zip_path = Path(local_path)
            
            if not zip_path.exists():
                logger.warning(f"⚠️ [{i}] 文件不存在: {local_path}")
                stats['skipped'] += 1
                continue
            
            logger.info(f"\n[{i}/{len(reports)}] 处理: {title}")
            
            success = self._extract_and_rename(zip_path, title)
            
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1
        
        self._print_stats(stats)
        return stats


if __name__ == "__main__":
    # 测试代码
    print("Downloader模块测试")
    print("请通过main.py运行完整测试")
    print("\n示例命令：")
    print("  python main.py --stage4 --max-reports 5")
    print("  python main.py --retry --max-reports 10")