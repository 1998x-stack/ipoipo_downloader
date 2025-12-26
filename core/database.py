"""
数据库管理 - 使用SQLite记录下载状态（修复版）

新增方法：
- get_ready_reports(): 获取ready状态的报告
- get_failed_reports(): 获取失败的报告
- update_report_local_path(): 更新本地文件路径
- get_reports_with_category(): 获取报告及分类名称
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path
from utils.logger import get_logger
from config.settings import DATABASE_PATH

logger = get_logger(__name__)


class Database:
    """数据库管理器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        self.conn = None
        self.init_database()
    
    def connect(self):
        """连接数据库"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def init_database(self):
        """初始化数据库表"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # 分类表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id TEXT UNIQUE NOT NULL,
                category_name TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 报告列表表（新增 local_path 字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id TEXT NOT NULL,
                post_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                detail_url TEXT NOT NULL,
                download_url TEXT,
                thumbnail_url TEXT,
                view_count INTEGER DEFAULT 0,
                publish_date TEXT,
                status TEXT DEFAULT 'pending',
                local_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        ''')
        
        # 下载记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                zip_url TEXT NOT NULL,
                file_name TEXT,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                download_attempts INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES reports(post_id)
            )
        ''')
        
        # 解压记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                download_id INTEGER NOT NULL,
                extract_path TEXT NOT NULL,
                files_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                extracted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (download_id) REFERENCES downloads(id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_downloads_post_id ON downloads(post_id)')
        
        # 检查并添加 local_path 列（兼容旧数据库）
        try:
            cursor.execute('SELECT local_path FROM reports LIMIT 1')
        except sqlite3.OperationalError:
            logger.info("📝 添加 local_path 列...")
            cursor.execute('ALTER TABLE reports ADD COLUMN local_path TEXT')
        
        conn.commit()
        logger.info("✅ 数据库初始化完成")
    
    # ===== 分类操作 =====
    
    def insert_category(self, category_id: str, category_name: str, url: str):
        """插入分类"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (category_id, category_name, url)
                VALUES (?, ?, ?)
            ''', (category_id, category_name, url))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ 插入分类失败: {e}")
            return False
    
    def get_all_categories(self) -> List[Dict]:
        """获取所有分类"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories ORDER BY category_id')
        return [dict(row) for row in cursor.fetchall()]
    
    def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        """根据ID获取分类"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories WHERE category_id = ?', (category_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ===== 报告操作 =====
    
    def insert_report(self, category_id: str, post_id: str, title: str, 
                      detail_url: str, **kwargs):
        """插入报告"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO reports 
                (category_id, post_id, title, detail_url, thumbnail_url, view_count, publish_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                category_id, post_id, title, detail_url,
                kwargs.get('thumbnail_url', ''),
                kwargs.get('view_count', 0),
                kwargs.get('publish_date', '')
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ 插入报告失败: {e}")
            return False
    
    def update_report_download_url(self, post_id: str, download_url: str):
        """更新报告的下载URL"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reports 
            SET download_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE post_id = ?
        ''', (download_url, post_id))
        conn.commit()
    
    def update_report_local_path(self, post_id: str, local_path: str):
        """更新报告的本地文件路径"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reports 
            SET local_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE post_id = ?
        ''', (local_path, post_id))
        conn.commit()
    
    def update_report_status(self, post_id: str, status: str):
        """更新报告状态"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reports 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE post_id = ?
        ''', (status, post_id))
        conn.commit()
    
    def get_report_by_post_id(self, post_id: str) -> Optional[Dict]:
        """根据post_id获取报告"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports WHERE post_id = ?', (post_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_reports_by_category(self, category_id: str, status: str = None) -> List[Dict]:
        """获取指定分类的报告（包含分类名称）"""
        conn = self.connect()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT r.*, c.category_name 
                FROM reports r
                LEFT JOIN categories c ON r.category_id = c.category_id
                WHERE r.category_id = ? AND r.status = ?
                ORDER BY r.id
            ''', (category_id, status))
        else:
            cursor.execute('''
                SELECT r.*, c.category_name 
                FROM reports r
                LEFT JOIN categories c ON r.category_id = c.category_id
                WHERE r.category_id = ?
                ORDER BY r.id
            ''', (category_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_pending_reports(self, limit: int = 100) -> List[Dict]:
        """获取待处理的报告（status='pending'，需要获取download_url）"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, c.category_name 
            FROM reports r
            LEFT JOIN categories c ON r.category_id = c.category_id
            WHERE r.status = 'pending'
            ORDER BY r.id
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_ready_reports(self, limit: int = 1000) -> List[Dict]:
        """获取准备下载的报告（status='ready'，已有download_url）"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, c.category_name 
            FROM reports r
            LEFT JOIN categories c ON r.category_id = c.category_id
            WHERE r.status = 'ready' AND r.download_url IS NOT NULL AND r.download_url != ''
            ORDER BY r.id
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_failed_reports(self, limit: int = 100) -> List[Dict]:
        """获取下载失败的报告（status='failed'）"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, c.category_name 
            FROM reports r
            LEFT JOIN categories c ON r.category_id = c.category_id
            WHERE r.status = 'failed' AND r.download_url IS NOT NULL AND r.download_url != ''
            ORDER BY r.id
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_downloaded_reports(self, limit: int = 1000) -> List[Dict]:
        """获取已下载的报告（status='downloaded'）"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, c.category_name 
            FROM reports r
            LEFT JOIN categories c ON r.category_id = c.category_id
            WHERE r.status = 'downloaded'
            ORDER BY r.id
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_reports_by_status(self, status: str, limit: int = 1000) -> List[Dict]:
        """根据状态获取报告"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, c.category_name 
            FROM reports r
            LEFT JOIN categories c ON r.category_id = c.category_id
            WHERE r.status = ?
            ORDER BY r.id
            LIMIT ?
        ''', (status, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== 下载记录操作 =====
    
    def insert_download(self, post_id: str, zip_url: str, file_name: str = None) -> int:
        """插入下载记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO downloads (post_id, zip_url, file_name, started_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (post_id, zip_url, file_name))
        conn.commit()
        return cursor.lastrowid
    
    def update_download_status(self, download_id: int, status: str, 
                               file_path: str = None, file_size: int = None,
                               error_message: str = None):
        """更新下载状态"""
        conn = self.connect()
        cursor = conn.cursor()
        
        if status == 'completed':
            cursor.execute('''
                UPDATE downloads 
                SET status = ?, file_path = ?, file_size = ?, 
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, file_path, file_size, download_id))
        elif status == 'failed':
            cursor.execute('''
                UPDATE downloads 
                SET status = ?, error_message = ?,
                    download_attempts = download_attempts + 1
                WHERE id = ?
            ''', (status, error_message, download_id))
        else:
            cursor.execute('''
                UPDATE downloads 
                SET status = ?
                WHERE id = ?
            ''', (status, download_id))
        
        conn.commit()
    
    def get_download_by_post_id(self, post_id: str) -> Optional[Dict]:
        """获取下载记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM downloads 
            WHERE post_id = ?
            ORDER BY id DESC
            LIMIT 1
        ''', (post_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def is_downloaded(self, post_id: str) -> bool:
        """检查是否已下载"""
        download = self.get_download_by_post_id(post_id)
        return download and download['status'] == 'completed'
    
    # ===== 批量操作 =====
    
    def batch_update_status(self, post_ids: List[str], status: str):
        """批量更新报告状态"""
        conn = self.connect()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in post_ids])
        cursor.execute(f'''
            UPDATE reports 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE post_id IN ({placeholders})
        ''', [status] + post_ids)
        
        conn.commit()
        return cursor.rowcount
    
    def reset_failed_reports(self) -> int:
        """重置所有失败的报告为ready状态"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reports 
            SET status = 'ready', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'failed' AND download_url IS NOT NULL
        ''')
        conn.commit()
        return cursor.rowcount
    
    # ===== 统计操作 =====
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = self.connect()
        cursor = conn.cursor()
        
        stats = {}
        
        # 总分类数
        cursor.execute('SELECT COUNT(*) FROM categories')
        stats['total_categories'] = cursor.fetchone()[0]
        
        # 总报告数
        cursor.execute('SELECT COUNT(*) FROM reports')
        stats['total_reports'] = cursor.fetchone()[0]
        
        # 各状态报告数
        cursor.execute('SELECT status, COUNT(*) FROM reports GROUP BY status')
        stats['reports_by_status'] = dict(cursor.fetchall())
        
        # 已下载数
        cursor.execute('SELECT COUNT(*) FROM downloads WHERE status = "completed"')
        stats['downloads_completed'] = cursor.fetchone()[0]
        
        # 下载失败数
        cursor.execute('SELECT COUNT(*) FROM downloads WHERE status = "failed"')
        stats['downloads_failed'] = cursor.fetchone()[0]
        
        # 有下载链接的报告数
        cursor.execute('SELECT COUNT(*) FROM reports WHERE download_url IS NOT NULL AND download_url != ""')
        stats['reports_with_url'] = cursor.fetchone()[0]
        
        # 各分类的报告数
        cursor.execute('''
            SELECT c.category_name, COUNT(r.id) as count
            FROM categories c
            LEFT JOIN reports r ON c.category_id = r.category_id
            GROUP BY c.category_id
            ORDER BY count DESC
        ''')
        stats['reports_by_category'] = dict(cursor.fetchall())
        
        return stats
    
    def get_category_stats(self, category_id: str) -> Dict:
        """获取指定分类的统计信息"""
        conn = self.connect()
        cursor = conn.cursor()
        
        stats = {}
        
        # 分类信息
        cursor.execute('SELECT * FROM categories WHERE category_id = ?', (category_id,))
        row = cursor.fetchone()
        if row:
            stats['category'] = dict(row)
        
        # 该分类的报告数
        cursor.execute('SELECT COUNT(*) FROM reports WHERE category_id = ?', (category_id,))
        stats['total_reports'] = cursor.fetchone()[0]
        
        # 各状态报告数
        cursor.execute('''
            SELECT status, COUNT(*) 
            FROM reports 
            WHERE category_id = ?
            GROUP BY status
        ''', (category_id,))
        stats['reports_by_status'] = dict(cursor.fetchall())
        
        return stats


if __name__ == "__main__":
    # 测试代码
    db = Database()
    
    # 插入测试数据
    db.insert_category("34", "经济报告", "https://ipoipo.cn/tags-34.html")
    db.insert_report("34", "26028", "测试报告", "https://ipoipo.cn/post/26028.html")
    
    # 更新下载URL
    db.update_report_download_url("26028", "https://ipo.ai-tag.cn/test.zip")
    db.update_report_status("26028", "ready")
    
    # 测试新方法
    print("\n📋 Ready reports:")
    ready = db.get_ready_reports(limit=10)
    for r in ready:
        print(f"  - {r['title']}: {r['status']}")
    
    print("\n📋 Failed reports:")
    failed = db.get_failed_reports(limit=10)
    for r in failed:
        print(f"  - {r['title']}: {r['status']}")
    
    # 获取统计
    print("\n📊 统计信息:")
    stats = db.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    db.close()