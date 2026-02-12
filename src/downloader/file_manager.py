"""
文件管理器 - 处理文件命名、路径和解压（修复版）

新增方法：
- get_report_path(): 获取报告文件保存路径
"""
import os
import re
import zipfile
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from src.utils.logger import get_logger
from src.config.settings import (
    DOWNLOAD_DIR, INVALID_CHARS, MAX_FILENAME_LENGTH,
    CATEGORY_NAMES
)

logger = get_logger(__name__)


class FileManager:
    """文件管理器"""
    
    # 扩展的非法字符集（包括中文标点）
    ILLEGAL_CHARS = r'[<>:"/\\|?*【】（）《》""''：；，。！？\[\]]'
    
    # 支持的文档扩展名
    DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls'}
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or DOWNLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, filename: str, is_folder: bool = False) -> str:
        """
        清理文件名（移除非法字符）
        
        Args:
            filename: 原始文件名
            is_folder: 是否为文件夹名（文件夹名更严格）
        """
        # 保留扩展名
        if not is_folder and '.' in filename:
            name, ext = os.path.splitext(filename)
        else:
            name, ext = filename, ''
        
        # 移除或替换非法字符
        name = re.sub(self.ILLEGAL_CHARS, '_', name)
        
        # 替换中文括号为下划线
        name = name.replace('（', '_').replace('）', '_')
        name = name.replace('【', '_').replace('】', '_')
        
        # 移除多余的空格、下划线和点
        name = re.sub(r'[_\s.]+', '_', name)
        name = name.strip('_. ')
        
        # 如果是文件夹，进一步清理
        if is_folder:
            # 只保留字母、数字、中文、下划线
            name = re.sub(r'[^\w\u4e00-\u9fff]+', '_', name)
            name = re.sub(r'_+', '_', name)
        
        # 限制长度
        max_len = MAX_FILENAME_LENGTH - len(ext) if ext else MAX_FILENAME_LENGTH
        if len(name) > max_len:
            name = name[:max_len]
        
        # 确保不为空
        if not name:
            name = "unnamed"
        
        return name + ext if ext else name
    
    def get_category_dir(self, category_name: str) -> Path:
        """
        获取分类目录
        
        Args:
            category_name: 分类名称（如 "经济报告"）
        """
        # 清理分类名称
        clean_name = self.sanitize_filename(category_name, is_folder=True)
        category_dir = self.base_dir / clean_name
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir
    
    def get_category_dir_by_id(self, category_id: str) -> Path:
        """
        根据分类ID获取分类目录
        
        Args:
            category_id: 分类ID（如 "34"）
        """
        category_name = CATEGORY_NAMES.get(category_id, f"category_{category_id}")
        return self.get_category_dir(category_name)
    
    def get_report_path(self, category_name: str, filename: str) -> str:
        """
        获取报告文件的完整保存路径
        
        Args:
            category_name: 分类名称（如 "经济报告"）
            filename: 文件名（如 "report.zip"）
            
        Returns:
            完整的文件路径字符串
        """
        # 获取分类目录
        category_dir = self.get_category_dir(category_name)
        
        # 清理文件名
        clean_filename = self.sanitize_filename(filename)
        
        # 返回完整路径
        return str(category_dir / clean_filename)
    
    def get_report_path_by_id(self, category_id: str, filename: str) -> str:
        """
        根据分类ID获取报告文件路径
        
        Args:
            category_id: 分类ID
            filename: 文件名
            
        Returns:
            完整的文件路径字符串
        """
        category_name = CATEGORY_NAMES.get(category_id, f"category_{category_id}")
        return self.get_report_path(category_name, filename)
    
    def get_report_dir(self, category_id: str, report_title: str) -> Path:
        """获取报告目录（每个报告单独一个目录）"""
        category_dir = self.get_category_dir_by_id(category_id)
        report_name = self.sanitize_filename(report_title, is_folder=True)
        report_dir = category_dir / report_name
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir
    
    def get_zip_path(self, category_id: str, report_title: str, zip_filename: str = None) -> Path:
        """获取ZIP文件路径"""
        report_dir = self.get_report_dir(category_id, report_title)
        
        if not zip_filename:
            zip_filename = "report.zip"
        else:
            zip_filename = self.sanitize_filename(zip_filename)
        
        return report_dir / zip_filename
    
    def extract_timestamp_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取时间戳
        
        支持的格式：
        - 202512040933142933045.zip -> 20251204
        - 20241225_report.zip -> 20241225
        - report_20241225.zip -> 20241225
        """
        # 尝试匹配 YYYYMMDD 格式（8位数字）
        patterns = [
            r'^(\d{8})',  # 开头的8位数字
            r'(\d{8})_',  # 后面跟下划线的8位数字
            r'_(\d{8})',  # 前面有下划线的8位数字
            r'(\d{14})',  # 14位时间戳，取前8位
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                timestamp = match.group(1)[:8]
                # 验证是否为有效日期
                try:
                    datetime.strptime(timestamp, '%Y%m%d')
                    return timestamp
                except ValueError:
                    continue
        
        # 如果没有找到，返回当前日期
        return datetime.now().strftime('%Y%m%d')
    
    def generate_new_filename(self, original_path: Path, report_title: str, 
                            timestamp: Optional[str] = None) -> str:
        """
        生成新的文件名
        
        格式：时间戳 + 报告标题 + 扩展名
        例如：20251204包装出海研究报告_纸包装_金属包装_塑料包装.pdf
        """
        ext = original_path.suffix
        
        # 如果没有提供时间戳，尝试从原文件名提取
        if not timestamp:
            timestamp = self.extract_timestamp_from_filename(original_path.stem)
        timestamp = str(timestamp)[:8]
        
        # 清理报告标题
        clean_title = self.sanitize_filename(report_title, is_folder=False)
        clean_title = clean_title.replace('.', '_').replace(" ", "")  # 移除标题中的点
        clean_title = clean_title.strip()
        
        # 组合新文件名
        new_filename = f"{timestamp}{clean_title}{ext}"
        
        return new_filename
    
    def rename_extracted_file(self, file_path: Path, report_title: str, 
                            timestamp: Optional[str] = None) -> Optional[Path]:
        """
        重命名解压后的文件
        
        Returns:
            新的文件路径，失败返回None
        """
        try:
            # 生成新文件名
            new_filename = self.generate_new_filename(file_path, report_title, timestamp)
            new_path = file_path.parent / new_filename
            
            # 如果新文件已存在，添加序号
            if new_path.exists() and new_path != file_path:
                base_name = new_path.stem
                ext = new_path.suffix
                counter = 1
                while new_path.exists():
                    new_path = file_path.parent / f"{base_name}_{counter}{ext}"
                    counter += 1
            
            # 重命名文件
            if file_path != new_path:
                file_path.rename(new_path)
                logger.info(f"📝 重命名: {file_path.name} -> {new_path.name}")
                return new_path
            
            return file_path
            
        except Exception as e:
            logger.error(f"❌ 重命名失败: {e}")
            return None
    
    def extract_zip(self, zip_path: Path, extract_to: Path = None, 
                   report_title: str = None, auto_rename: bool = True) -> Optional[Path]:
        """
        解压ZIP文件并自动重命名文档
        
        Args:
            zip_path: ZIP文件路径
            extract_to: 解压目标目录
            report_title: 报告标题（用于重命名）
            auto_rename: 是否自动重命名文档文件
        """
        try:
            if not zip_path.exists():
                logger.error(f"❌ ZIP文件不存在: {zip_path}")
                return None
            
            # 验证是否为有效的ZIP文件
            if not zipfile.is_zipfile(zip_path):
                logger.error(f"❌ 无效的ZIP文件: {zip_path}")
                # 尝试读取文件头部以诊断问题
                try:
                    with open(zip_path, 'rb') as f:
                        header = f.read(4)
                        logger.debug(f"文件头: {header.hex()}")
                except Exception as e:
                    logger.error(f"❌ 无法读取文件: {e}")
                return None
            
            # 默认解压到同一目录
            if extract_to is None:
                extract_to = zip_path.parent
            
            extract_to.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📦 解压文件: {zip_path.name}")
            logger.info(f"📁 目标目录: {extract_to}")
            
            # 从ZIP文件名提取时间戳
            timestamp = self.extract_timestamp_from_filename(zip_path.name)
            logger.info(f"🕐 提取时间戳: {timestamp}")
            
            extracted_files = []
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取文件列表
                file_list = zip_ref.namelist()
                logger.info(f"📋 包含 {len(file_list)} 个文件")
                
                # 解压所有文件
                for filename in file_list:
                    try:
                        # 清理文件名中的非法字符
                        clean_filename = self.sanitize_filename(filename)
                        target_path = extract_to / clean_filename
                        
                        # 创建父目录
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 解压文件
                        with zip_ref.open(filename) as source, open(target_path, 'wb') as target:
                            target.write(source.read())
                        
                        extracted_files.append(target_path)
                        logger.debug(f"  ✓ {clean_filename}")
                        
                    except Exception as e:
                        logger.warning(f"  ✗ 解压失败 {filename}: {e}")
                        continue
            
            logger.info(f"✅ 成功解压 {len(extracted_files)} 个文件")
            
            # 自动重命名文档文件
            if auto_rename and report_title and extracted_files:
                logger.info(f"🔄 开始重命名文档文件...")
                renamed_count = 0
                
                for file_path in extracted_files:
                    if file_path.suffix.lower() in self.DOCUMENT_EXTENSIONS:
                        new_path = self.rename_extracted_file(
                            file_path, 
                            report_title, 
                            timestamp
                        )
                        if new_path:
                            renamed_count += 1
                
                logger.info(f"✅ 重命名完成: {renamed_count} 个文档文件")
            
            return extract_to
            
        except zipfile.BadZipFile:
            logger.error(f"❌ ZIP文件损坏或格式错误: {zip_path}")
            return None
        except Exception as e:
            logger.error(f"❌ 解压失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def get_extracted_files(self, extract_dir: Path, 
                          extensions: Optional[set] = None) -> List[Path]:
        """
        获取解压后的文件
        
        Args:
            extract_dir: 解压目录
            extensions: 文件扩展名过滤（如 {'.pdf', '.docx'}）
        """
        if not extract_dir.exists():
            return []
        
        files = []
        for item in extract_dir.rglob('*'):
            if item.is_file():
                if extensions is None or item.suffix.lower() in extensions:
                    files.append(item)
        
        return files
    
    def cleanup_zip(self, zip_path: Path, keep_zip: bool = True):
        """清理ZIP文件"""
        try:
            if not keep_zip and zip_path.exists():
                zip_path.unlink()
                logger.info(f"🗑️ 删除ZIP文件: {zip_path.name}")
        except Exception as e:
            logger.error(f"❌ 删除ZIP失败: {e}")
    
    def get_file_size(self, file_path: Path) -> int:
        """获取文件大小（字节）"""
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except Exception:
            return 0
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def check_disk_space(self, required_bytes: int = 0) -> bool:
        """检查磁盘空间"""
        try:
            import shutil
            stat = shutil.disk_usage(self.base_dir)
            free_space = stat.free
            
            if required_bytes > 0:
                return free_space >= required_bytes
            
            # 默认检查至少有1GB空间
            return free_space >= 1024 * 1024 * 1024
        except Exception as e:
            logger.error(f"❌ 检查磁盘空间失败: {e}")
            return True  # 假设有足够空间
    
    def validate_and_fix_zip(self, zip_path: Path) -> bool:
        """
        验证并尝试修复ZIP文件
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # 检查文件是否存在
            if not zip_path.exists():
                logger.error(f"❌ 文件不存在: {zip_path}")
                return False
            
            # 检查文件大小
            file_size = self.get_file_size(zip_path)
            if file_size == 0:
                logger.error(f"❌ 文件为空: {zip_path}")
                return False
            
            # 验证ZIP格式
            if not zipfile.is_zipfile(zip_path):
                logger.error(f"❌ 不是有效的ZIP文件: {zip_path}")
                return False
            
            # 尝试打开并读取文件列表
            with zipfile.ZipFile(zip_path, 'r') as zf:
                file_list = zf.namelist()
                if not file_list:
                    logger.warning(f"⚠️ ZIP文件为空: {zip_path}")
                    return False
                
                # 测试ZIP完整性
                bad_file = zf.testzip()
                if bad_file:
                    logger.error(f"❌ ZIP文件损坏，首个损坏文件: {bad_file}")
                    return False
            
            logger.info(f"✅ ZIP文件验证通过: {zip_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ ZIP验证失败: {e}")
            return False
    
    def ensure_directory(self, path: str) -> Path:
        """确保目录存在"""
        dir_path = Path(path)
        if dir_path.suffix:
            # 如果是文件路径，获取父目录
            dir_path = dir_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path


if __name__ == "__main__":
    # 测试代码
    fm = FileManager()
    
    print("=" * 60)
    print("测试1: 文件名清理")
    print("=" * 60)
    test_names = [
        "包装出海研究报告：纸包装、金属包装、塑料包装（33页）",
        "2024年<新能源>行业分析：趋势/展望",
        "中国地方【公共数据】开放利用报告（55页）",
        "报告《2024》—第一季度.pdf",
        "文件名" * 50,  # 超长文件名
    ]
    
    for name in test_names:
        clean_name = fm.sanitize_filename(name, is_folder=True)
        print(f"原始: {name}")
        print(f"清理: {clean_name}\n")
    
    print("=" * 60)
    print("测试2: get_report_path")
    print("=" * 60)
    
    path = fm.get_report_path("经济报告", "202504291200327477262.zip")
    print(f"分类: 经济报告")
    print(f"文件名: 202504291200327477262.zip")
    print(f"完整路径: {path}")
    
    print("\n" + "=" * 60)
    print("测试3: 时间戳提取")
    print("=" * 60)
    test_timestamps = [
        "202512040933142933045.zip",
        "20241225_report.zip",
        "report_20241225.zip",
        "no_timestamp.zip",
    ]
    
    for filename in test_timestamps:
        timestamp = fm.extract_timestamp_from_filename(filename)
        print(f"{filename} -> {timestamp}")
    
    print("\n" + "=" * 60)
    print("测试4: 新文件名生成")
    print("=" * 60)
    test_file = Path("202512040933142933045.zip")
    report_title = "包装出海研究报告：纸包装、金属包装、塑料包装（33页）"
    new_name = fm.generate_new_filename(
        test_file.with_suffix('.pdf'), 
        report_title
    )
    print(f"报告标题: {report_title}")
    print(f"生成文件名: {new_name}")