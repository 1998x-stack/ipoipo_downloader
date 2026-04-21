"""CLI entry point for ipoipo downloader."""
import sys
import argparse
from config import USE_PROXY, PROXY_CONFIG_PATH, LOG_DIR, DATA_DIR
from logger import get_logger
from storage import Storage
from proxy import ProxyManager
from scraper import Scraper
from downloader import Downloader


def main():
    parser = argparse.ArgumentParser(description="ipoipo.cn report downloader")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--stage1", action="store_true", help="Stage 1: categories")
    parser.add_argument("--stage2", action="store_true", help="Stage 2: report lists")
    parser.add_argument("--stage3", action="store_true", help="Stage 3: download URLs")
    parser.add_argument("--stage4", action="store_true", help="Stage 4: download reports")
    parser.add_argument("--retry", action="store_true", help="Retry failed downloads")
    parser.add_argument("--extract", action="store_true", help="Extract ZIPs only")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--max-pages", type=int, help="Max pages per category")
    parser.add_argument("--max-reports", type=int, help="Max reports to process")
    parser.add_argument("--limit", type=int, help="Limit for stage 3")
    parser.add_argument("--category", type=str, help="Category ID")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy")
    parser.add_argument("--keep-zip", action="store_true", help="Keep ZIP after extraction")
    args = parser.parse_args()

    if not any([args.full, args.stage1, args.stage2, args.stage3, args.stage4, args.retry, args.extract, args.stats]):
        parser.print_help()
        sys.exit(0)

    use_proxy = not args.no_proxy and USE_PROXY
    log = get_logger("main", jsonl_path=str(LOG_DIR / "events.jsonl"))
    storage = Storage(str(DATA_DIR))

    proxy_manager = None
    if use_proxy:
        try:
            proxy_manager = ProxyManager(str(PROXY_CONFIG_PATH))
            proxy_manager.test_all_nodes()
            proxy_manager.select_random()
            log.ok(f"Proxy: {proxy_manager.current_node.name}")
        except Exception as e:
            log.error(f"Proxy init failed: {e}, continuing without proxy")
            use_proxy = False

    scraper = Scraper(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)
    dl = Downloader(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)

    try:
        if args.stats:
            stats = storage.get_stats()
            log.info(f"Categories: {stats['total_categories']}")
            log.info(f"Reports: {stats['total_reports']}")
            log.info(f"By status: {stats['by_status']}")

        if args.stage1:
            scraper.scrape_categories()

        if args.stage2:
            if args.category:
                cat = storage.get_state("categories", args.category)
                if cat:
                    scraper.scrape_category(cat["category_id"], cat["category_name"], max_pages=args.max_pages)
                else:
                    log.error(f"Category {args.category} not found. Run --stage1 first.")
            else:
                scraper.scrape_all_categories(max_pages=args.max_pages)

        if args.stage3:
            scraper.process_pending_reports(limit=args.limit)

        if args.stage4:
            ready = storage.query_by_status("reports", "ready")
            if args.category:
                ready = [r for r in ready if r.get("category_id") == args.category]
                log.info(f"Filtered to category {args.category}: {len(ready)} reports")
            if args.max_reports:
                ready = ready[:args.max_reports]
            dl.download_all_ready(max_reports=len(ready), keep_zip=args.keep_zip, reports=ready)

        if args.retry:
            failed = storage.query_by_status("reports", "failed")
            if args.max_reports:
                failed = failed[:args.max_reports]
            log.info(f"Retrying {len(failed)} failed reports")
            for r in failed:
                storage.append("reports", {
                    "type": "url_found",
                    "post_id": r["post_id"],
                    "download_url": r.get("download_url", ""),
                })
            dl.download_all_ready(max_reports=len(failed), keep_zip=args.keep_zip)

        if args.extract:
            dl.extract_downloaded_zips(max_reports=args.max_reports, keep_zip=args.keep_zip, category=args.category)

        if args.full:
            scraper.scrape_categories()
            scraper.scrape_all_categories(max_pages=args.max_pages)
            scraper.process_pending_reports(limit=args.limit)
            dl.download_all_ready(max_reports=args.max_reports, keep_zip=args.keep_zip)

        if not args.stats:
            stats = storage.get_stats()
            log.info(f"Final stats: {stats}")

    except KeyboardInterrupt:
        log.warn("Interrupted by user")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        scraper.close()
        dl.close()
        storage.close()
        log.close()


if __name__ == "__main__":
    main()
