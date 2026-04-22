"""CLI entry point for ipoipo downloader.

Provides command-line interface and orchestrates the 4-stage pipeline:
categories discovery → report listing → URL extraction → ZIP download.
Supports both sequential single-stage execution and parallel multi-stage
execution with producer-consumer threading pattern.
"""
import sys
import time
import argparse
import threading
from typing import List, Optional, Tuple

from config import USE_PROXY, PROXY_CONFIG_PATH, LOG_DIR, DATA_DIR
from logger import Logger, get_logger
from storage import Storage
from proxy import ProxyManager
from scraper import Scraper
from downloader import Downloader


def run_parallel_pipeline(
    storage: Storage,
    log: Logger,
    use_proxy: bool,
    proxy_manager: Optional[ProxyManager],
    max_pages: Optional[int],
    max_reports: Optional[int],
    limit: Optional[int],
    keep_zip: bool,
    resume: bool,
) -> None:
    """Run stages 2, 3, and 4 concurrently using a producer-consumer pattern.

    This function launches three threads that work together:
    - Stage 2 (producer): Scrapes categories and populates reports.jsonl with
      "pending" entries.
    - Stage 3 (consumer of Stage 2, producer for Stage 4): Polls for pending
      reports, extracts download URLs, and writes "url_found" events that
      transition reports to "ready" status.
    - Stage 4 (consumer of Stage 3): Polls for ready reports and downloads
      ZIP files.

    Stages 3 and 4 start immediately and poll every 15 seconds while Stage 2
    is still producing data. This overlapping design allows the pipeline to
    begin processing reports as soon as they are discovered, rather than
    waiting for all categories to be fully scraped.

    Args:
        storage: JSONL storage instance for reading/writing pipeline state.
        log: Logger instance for console and file output.
        use_proxy: Whether to enable proxy for HTTP requests.
        proxy_manager: Proxy manager for node selection and failover.
            Can be None if proxy is disabled or initialization failed.
        max_pages: Maximum pages to scrape per category. None for unlimited.
        max_reports: Maximum reports to download. None for unlimited.
        limit: Maximum reports to process per batch in Stage 3.
            None defaults to 50.
        keep_zip: Whether to retain ZIP files after extraction.
        resume: Whether to skip already-downloaded reports.

    Raises:
        RuntimeError: If any stage thread encounters an unhandled exception.
    """
    # 同步原语：用于通知 Stage 2 和 Stage 3 是否已完成
    # Stage 3 和 Stage 4 通过检测这些事件来决定何时退出轮询循环
    stage2_done = threading.Event()
    stage3_done = threading.Event()

    # 线程安全的错误收集器：各 worker 将异常追加到此列表
    errors: List[Tuple[str, Exception]] = []
    errors_lock = threading.Lock()

    # 为每个阶段创建独立的 Scraper/Downloader 实例，
    # 避免共享 session 导致 cookies 和代理状态互相干扰
    scraper_stage2 = Scraper(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)
    scraper_stage3 = Scraper(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)
    downloader = Downloader(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)

    def stage2_worker() -> None:
        """Stage 2 worker: scrape categories and report lists (producer)."""
        try:
            # 先发现所有分类，再遍历每个分类的报告列表
            scraper_stage2.scrape_categories(resume=resume)
            scraper_stage2.scrape_all_categories(max_pages=max_pages, resume=resume)
        except Exception as error:
            with errors_lock:
                errors.append(("Stage2", error))
            log.error(f"Stage 2 failed: {error}")
        finally:
            # 通知 Stage 3 和 Stage 4：数据生产已结束
            stage2_done.set()
            scraper_stage2.close()

    def stage3_worker() -> None:
        """Stage 3 worker: extract download URLs from pending reports.

        轮询逻辑：
        1. 优先处理 pending 状态的报告（Stage 2 正在生产数据时）。
        2. 当没有 pending 报告且 Stage 2 已完成时，做最后一次全量处理并退出。
        3. 否则等待 15 秒后重试。
        """
        try:
            while True:
                pending = storage.query_by_status("reports", "pending")
                if pending:
                    # 有待处理报告时，按批次限制处理
                    batch_limit = limit if limit else 50
                    scraper_stage3.process_pending_reports(limit=batch_limit)
                elif stage2_done.is_set():
                    # Stage 2 已完成且无 pending 报告：最后一次全量处理后退出
                    scraper_stage3.process_pending_reports(limit=None)
                    break
                else:
                    # Stage 2 仍在运行但暂无 pending 报告，等待后重试
                    time.sleep(15)
        except Exception as error:
            with errors_lock:
                errors.append(("Stage3", error))
            log.error(f"Stage 3 failed: {error}")
        finally:
            stage3_done.set()
            scraper_stage3.close()

    def stage4_worker() -> None:
        """Stage 4 worker: download ZIP files from ready reports.

        轮询逻辑：
        1. 查询 ready 状态的报告并下载。
        2. 启用 resume 时，额外过滤掉磁盘上已存在的报告。
        3. 当 Stage 2 和 Stage 3 都已完成且无 ready 报告时退出。
        4. 否则等待 15 秒后重试。
        """
        try:
            while True:
                ready = storage.query_by_status("reports", "ready")
                if resume:
                    # resume 模式下额外检查磁盘文件，避免重复下载
                    ready = [
                        report
                        for report in ready
                        if not storage.is_report_downloaded(report["post_id"])
                    ]
                if ready:
                    # 按 max_reports 限制下载数量
                    batch = ready[:20] if max_reports is None else ready[:max_reports]
                    downloader.download_all_ready(
                        max_reports=len(batch), keep_zip=keep_zip, reports=batch
                    )
                elif stage2_done.is_set() and stage3_done.is_set():
                    # 所有上游阶段已完成且无 ready 报告，安全退出
                    break
                else:
                    time.sleep(15)
        except Exception as error:
            with errors_lock:
                errors.append(("Stage4", error))
            log.error(f"Stage 4 failed: {error}")
        finally:
            downloader.close()

    thread_stage2 = threading.Thread(target=stage2_worker, name="Stage2")
    thread_stage3 = threading.Thread(target=stage3_worker, name="Stage3")
    thread_stage4 = threading.Thread(target=stage4_worker, name="Stage4")

    # 先启动消费者（Stage 3/4），再启动生产者（Stage 2）
    # 消费者可在生产者生成数据的同时开始处理
    thread_stage3.start()
    thread_stage4.start()
    thread_stage2.start()

    thread_stage2.join()
    thread_stage3.join()
    thread_stage4.join()
    if errors:
        for stage_name, error in errors:
            log.error(f"{stage_name} error: {error}")
        raise RuntimeError(f"Pipeline failed: {len(errors)} stage(s) errored")


def main() -> None:
    """CLI entry point: parse arguments and dispatch pipeline stages.

    Supports two execution modes:
    1. Single-stage mode: Run individual stages (--stage1 through --stage4)
       or utility commands (--retry, --extract, --stats).
    2. Full pipeline mode: Run all stages concurrently via --full flag,
       using the parallel producer-consumer pattern in run_parallel_pipeline().

    Exits with code 0 on success, code 1 on fatal error.
    """
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
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint (skip completed)")
    args = parser.parse_args()

    # 未提供任何操作标志时，显示帮助信息并退出
    if not any([
        args.full, args.stage1, args.stage2, args.stage3, args.stage4,
        args.retry, args.extract, args.stats,
    ]):
        parser.print_help()
        sys.exit(0)

    # 根据 --no-proxy 标志和环境变量决定是否启用代理
    use_proxy = not args.no_proxy and USE_PROXY
    log = get_logger("main", jsonl_path=str(LOG_DIR / "events.jsonl"))
    storage = Storage(str(DATA_DIR))

    # 初始化代理管理器：失败时自动降级为无代理模式
    proxy_manager: Optional[ProxyManager] = None
    if use_proxy:
        try:
            proxy_manager = ProxyManager(str(PROXY_CONFIG_PATH))
            proxy_manager.test_all_nodes()
            proxy_manager.select_random()
            log.ok(f"Proxy: {proxy_manager.current_node.name}")
        except Exception as error:
            log.error(f"Proxy init failed: {error}, continuing without proxy")
            use_proxy = False

    scraper = Scraper(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)
    downloader = Downloader(storage, log, use_proxy=use_proxy, proxy_manager=proxy_manager)

    try:
        if args.stats:
            stats = storage.get_stats()
            log.info(f"Categories: {stats['total_categories']}")
            log.info(f"Reports: {stats['total_reports']}")
            log.info(f"By status: {stats['by_status']}")

        if args.stage1:
            scraper.scrape_categories(resume=args.resume)

        if args.stage2:
            if args.category:
                # 按指定分类 ID 抓取报告列表
                category = storage.get_state("categories", args.category)
                if category:
                    existing_count = storage.get_category_report_count(args.category)
                    if args.resume and existing_count > 0:
                        log.info(
                            f"Category {args.category} already has "
                            f"{existing_count} reports, skipping"
                        )
                    else:
                        scraper.scrape_category(
                            category["category_id"],
                            category["category_name"],
                            max_pages=args.max_pages,
                        )
                else:
                    log.error(f"Category {args.category} not found. Run --stage1 first.")
            else:
                scraper.scrape_all_categories(max_pages=args.max_pages, resume=args.resume)

        if args.stage3:
            scraper.process_pending_reports(limit=args.limit)

        if args.stage4:
            ready = storage.query_by_status("reports", "ready")
            if args.resume:
                # resume 模式下额外过滤磁盘上已存在的报告
                ready = [
                    report
                    for report in ready
                    if not storage.is_report_downloaded(report["post_id"])
                ]
            if args.category:
                ready = [
                    report
                    for report in ready
                    if report.get("category_id") == args.category
                ]
                log.info(f"Filtered to category {args.category}: {len(ready)} reports")
            if args.max_reports:
                ready = ready[:args.max_reports]
            downloader.download_all_ready(
                max_reports=len(ready), keep_zip=args.keep_zip, reports=ready
            )

        if args.retry:
            failed = storage.query_by_status("reports", "failed")
            if args.max_reports:
                failed = failed[:args.max_reports]
            log.info(f"Retrying {len(failed)} failed reports")
            for report in failed:
                storage.append("reports", {
                    "type": "url_found",
                    "post_id": report["post_id"],
                    "download_url": report.get("download_url", ""),
                })
            downloader.download_all_ready(
                max_reports=len(failed), keep_zip=args.keep_zip
            )

        if args.extract:
            downloader.extract_downloaded_zips(
                max_reports=args.max_reports,
                keep_zip=args.keep_zip,
                category=args.category,
            )

        if args.full:
            run_parallel_pipeline(
                storage, log, use_proxy, proxy_manager,
                max_pages=args.max_pages, max_reports=args.max_reports,
                limit=args.limit, keep_zip=args.keep_zip, resume=args.resume,
            )

        if not args.stats:
            stats = storage.get_stats()
            log.info(f"Final stats: {stats}")

    except KeyboardInterrupt:
        log.warn("Interrupted by user")
    except Exception as error:
        log.error(f"Fatal error: {error}")
        sys.exit(1)
    finally:
        scraper.close()
        downloader.close()
        storage.close()
        log.close()


if __name__ == "__main__":
    main()
