"""New package CLI preserving familiar --full/--stageN entrypoints."""
import argparse
import json
from pathlib import Path
import sys

from ipoipo.observability.logging import configure_logging
from ipoipo.persistence.event_log import export_events
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
    p.add_argument("--no-proxy", action="store_true")
    p.add_argument("--keep-zip", action="store_true")
    p.add_argument("--export-events", type=Path)
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
    settings = Settings(data_dir=args.data_dir,
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
            if args.export_events:
                result["exported_events"] = export_events(runner.repository, args.export_events)
            if not result:
                make_parser().print_help()
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        runner.close()


if __name__ == "__main__":
    sys.exit(main())
