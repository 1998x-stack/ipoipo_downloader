# Changelog

All notable changes to the ipoipo downloader project.

---

## [2.0.0] — 2026-04-22 — Complete Redesign

### Breaking Changes

- **SQLite → JSONL storage**: `data/downloads.db` replaced with `data/categories.jsonl`, `data/reports.jsonl`, `data/downloads.jsonl`. No migration path — start fresh.
- **Module restructure**: Old `core/`, `scrapers/`, `download/` directories replaced with flat modules (`scraper.py`, `downloader.py`, `storage.py`, `proxy.py`, `logger.py`).
- **Proxy config gitignored**: `config/proxy.yaml` is no longer tracked. Users must provide their own Clash config.
- **Removed dependencies**: `loguru`, `aiohttp`, `aiofiles`, `tqdm`, `fake-headers` no longer required.

### New Features

- **JSONL storage**: Append-only event log with status derivation from last event per entity. No explicit state field needed.
- **Dual-output logging**: Colored console output for real-time monitoring + structured JSONL file (`logs/events.jsonl`) for post-run analysis.
- **Domain-driven modules**: Clean separation — `scraper.py` (Stages 1-3), `downloader.py` (Stage 4), `storage.py`, `logger.py`, `proxy.py`, `utils/`.
- **Shell scripts**: `scripts/run.sh` (background runner), `scripts/run_stage.sh` (single stage), `scripts/stats.sh` (JSONL stats).
- **`--extract` command**: Extract downloaded ZIPs without re-downloading.
- **`--keep-zip` flag**: Retain ZIP files after extraction.
- **`USE_PROXY` env variable**: Control proxy usage via environment (`USE_PROXY=false`).

### Bug Fixes

- **Method name collision**: `scrape_all_categories` was defined twice (Stage 1 and Stage 2). Renamed Stage 1 to `scrape_categories()`.
- **Consecutive failure counter not reset**: After proxy switch, the failure counter was not reset, causing immediate re-switch on next failure. Fixed in `downloader.py`.
- **`extract_downloaded_zips` used category name as title**: Produced incorrect filenames. Now queries storage for report title first.
- **Unused imports**: Removed `re`, `time`, `urljoin`, `sys` from various modules.
- **Type hints**: Fixed `max_latency: int = None` → `Optional[int]`, `visit_download_page` return type → `Tuple[bool, Optional[str], str]`.
- **Mock return value mismatch**: Test mock returned 3-tuple but `_download_zip` returns 2-tuple.
- **Redundant char replacements**: `sanitize.py` had duplicate `.replace()` calls for characters already covered by regex.
- **Import inside method**: Moved `concurrent.futures` import to top-level in `proxy.py`.

### Improvements

- **Logger context manager**: Added `__enter__`/`__exit__` for safe resource cleanup.
- **Download stats**: `get_stats()` now counts unique download post_ids instead of raw line count.
- **Dedup test**: Fixed `test_dedup_on_startup` to actually test dedup behavior (was appending to closed handle).
- **`if limit:` → `if limit is not None:`**: Prevents `limit=0` from being treated as falsy.

### Architecture

```
Before (v1):                              After (v2):
main.py                                   main.py
├── core/                                 ├── scraper.py (Stages 1-3)
│   ├── http_client.py                    ├── downloader.py (Stage 4)
│   ├── database.py (SQLite)              ├── storage.py (JSONL)
│   └── proxy_manager.py                  ├── proxy.py
├── scrapers/                             ├── logger.py (dual output)
│   ├── category_scraper.py               ├── config.py
│   ├── list_scraper.py                   └── utils/
│   └── download_scraper.py                   ├── headers.py
├── download/                                 ├── sanitize.py
│   ├── downloader.py                         └── helpers.py
│   └── file_manager.py
└── utils/
    └── logger.py (loguru)
```

### Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| utils | 15 | ✅ |
| logger | 5 | ✅ |
| storage | 8 | ✅ |
| proxy | 5 | ✅ |
| scraper | 3 | ✅ |
| downloader | 4 | ✅ |
| **Total** | **40** | **✅** |

---

## [1.0.0] — Pre-redesign (archived on `main` branch)

- SQLite-based storage
- loguru logging
- Monolithic module structure (`core/`, `scrapers/`, `download/`)
- Anti-hotlinking bypass with Tengine CDN Referer fix
- Proxy auto-switch on 403
- Concurrent download support (`--concurrent`)
