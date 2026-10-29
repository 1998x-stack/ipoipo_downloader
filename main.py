"""Backward-compatible script entrypoint for the v3 package CLI.

The legacy --extract command is still available for archives stored under
data/downloads, without changing the new validated v3 artifact pipeline.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from ipoipo.cli import main  # noqa: E402


def extract_legacy(argv):
    parser = argparse.ArgumentParser(description="Extract old ZIP archives (legacy only)")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--category")
    parser.add_argument("--max-reports", type=int)
    parser.add_argument("--keep-zip", action="store_true")
    args = parser.parse_args(argv)
    from downloader import Downloader
    from logger import get_logger
    from storage import Storage
    logger = get_logger("legacy-extract")
    storage = Storage(str(ROOT / "data"))
    downloader = Downloader(storage, logger, use_proxy=False)
    try:
        downloader.extract_downloaded_zips(
            max_reports=args.max_reports, keep_zip=args.keep_zip, category=args.category
        )
    finally:
        downloader.close()
        storage.close()
        logger.close()
    return 0


if __name__ == "__main__":
    if "--extract" in sys.argv[1:]:
        sys.exit(extract_legacy(sys.argv[1:]))
    sys.exit(main())
