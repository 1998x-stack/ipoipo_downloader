"""New package CLI preserving familiar --full/--stageN entrypoints."""
import argparse
import json
import os
from pathlib import Path
import sys

from ipoipo.observability.logging import configure_logging
from ipoipo.persistence.event_log import export_events
from ipoipo.persistence.legacy_import import import_legacy
from ipoipo.pipeline.legacy_archive import migrate_archives
from ipoipo.pipeline.runner import PipelineRunner
from ipoipo.settings import Settings


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ipoipo", description="Auditable industry report collector v3")
    for name in ("full", "stage1", "stage2", "stage3", "stage4", "stats", "retry"):
        p.add_argument("--" + name, action="store_true")
    p.add_argument("--category")
    p.add_argument("--max-pages", type=int)
    p.add_argument("--max-reports", type=int)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--incremental", action="store_true")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--proxy-url")
    p.add_argument("--proxy-controller-url",
                   help="Loopback Clash/Mihomo API URL; never remote")
    p.add_argument("--proxy-group", help="Local proxy selection group")
    p.add_argument("--proxy-node", help="Explicitly select an allowed node")
    p.add_argument("--check-proxy-egress", action="store_true",
                   help="Opt-in call to ipify through the configured proxy")
    p.add_argument("--no-proxy", action="store_true")
    p.add_argument("--keep-zip", action="store_true")
    p.add_argument("--extract", action="store_true",
                   help="Safely import existing local ZIPs; original files are unchanged")
    p.add_argument("--archive-dir", type=Path,
                   help="Source ZIP directory; defaults to data/downloads")
    p.add_argument("--export-events", type=Path)
    p.add_argument("--import-legacy", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.max_reports is not None and args.max_reports < 1:
        raise SystemExit("--max-reports must be positive")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.category is not None and not args.category.isdigit():
        raise SystemExit("--category must be numeric")
    configure_logging(args.verbose)
    if args.no_proxy and (args.proxy_node or args.check_proxy_egress):
        raise SystemExit("--no-proxy conflicts with proxy selection/diagnostics")
    settings = Settings(data_dir=args.data_dir,
                        proxy_controller_url=args.proxy_controller_url,
                        proxy_group=args.proxy_group, proxy_node=args.proxy_node,
                        proxy_controller_token=os.environ.get("IPOIPO_PROXY_CONTROLLER_TOKEN"),
                        check_proxy_egress=args.check_proxy_egress,
                        proxy_url=None if args.no_proxy else args.proxy_url,
                        keep_zip=args.keep_zip)
    runner = PipelineRunner(settings)
    try:
        if args.full:
            result = runner.run_full(category_id=args.category, max_pages=args.max_pages,
                                     max_reports=args.max_reports, limit=args.limit,
                                     resume=args.resume, incremental=args.incremental)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            result = {}
            if args.extract:
                result["local_archive_import"] = migrate_archives(
                    settings, runner.repository,
                    args.archive_dir or args.data_dir / "downloads",
                    category=args.category, limit=args.max_reports
                )
            if args.import_legacy:
                result["legacy_import"] = import_legacy(args.data_dir, runner.repository)
            if args.retry:
                result["retry_reset"] = runner.repository.retry_failed()
            if args.stage1:
                result["seed_categories"] = runner.seed_categories()
            if args.stage2:
                result["discovery"] = runner.discover(
                    category_id=args.category, max_pages=args.max_pages,
                    resume=args.resume, incremental=args.incremental)
            if args.stage3 or args.stage4:
                result["recovery"] = runner.startup_recovery()
            if args.stage3:
                result["resolution"] = vars(runner.resolve_pending(limit=args.limit,
                                                                     category_id=args.category))
            if args.stage4:
                result["downloads"] = vars(runner.download_ready(limit=args.max_reports,
                                                                    category_id=args.category))
            if args.stats:
                result["stats"] = runner.repository.stats()
                if runner.proxy_diagnostics:
                    result["proxy"] = runner.proxy_diagnostics
            if args.export_events:
                result["exported_events"] = export_events(runner.repository, args.export_events)
            if not result:
                make_parser().print_help()
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if result.get("local_archive_import", {}).get("failed", 0):
                    return 1
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        runner.close()


if __name__ == "__main__":
    sys.exit(main())
