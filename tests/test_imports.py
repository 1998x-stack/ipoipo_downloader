"""
Basic import tests to verify the reorganized structure works correctly.
"""

def test_imports():
    """Test that all modules can be imported correctly."""
    try:
        import sys
        import os
        # Add project root to path to import modules
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        
        from src.utils.logger import get_logger
        from src.model.proxy_manager import ProxyManager
        from src.model.http_client import HTTPClient
        from src.model.database import Database
        from src.downloader.file_manager import FileManager
        from src.scraper.category_scraper import CategoryScraper
        from src.scraper.list_scraper import ListScraper
        from src.scraper.download_scraper import DownloadScraper
        from src.downloader.downloader import Downloader
        from src.config.settings import USE_PROXY
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()