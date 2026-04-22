# AGENTS.md — ipoipo Downloader

Python 3.10+ scraper/downloader for IPO industry reports from [ipoipo.cn](https://ipoipo.cn).

## Commands

```bash
pip install -r requirements.txt          # setup
python main.py --full --max-pages 2 --max-reports 10  # test run (full pipeline, limited)
python main.py --full --resume           # resume from checkpoint
python -m pytest                         # run all 44 tests
python -m pytest tests/test_storage.py   # run single module
bash scripts/stats.sh                    # quick pipeline stats
```

## Architecture

4-stage pipeline, flat module layout (no packages):

| File | Role |
|------|------|
| `main.py` | CLI + parallel orchestration (threading) |
| `scraper.py` | Stages 1-3: category discovery, report listing, URL extraction |
| `downloader.py` | Stage 4: ZIP download, extraction, rename |
| `storage.py` | Append-only JSONL event log; status derived from last event per `post_id` |
| `logger.py` | Dual output: colored console + JSONL file |
| `proxy.py` | Clash YAML parsing, SS-only node selection, auto-switch on 403 |
| `config.py` | All constants + `USE_PROXY` env var (default `true`) |
| `utils/` | `headers.py`, `sanitize.py`, `helpers.py` (retry decorator, jitter sleep) |

## Storage

JSONL files in `data/` — **append-only, no compaction**:
- `categories.jsonl` — discovered categories
- `reports.jsonl` — report events (`report_found` → `url_found` → `download_completed`/`download_failed`)
- `downloads.jsonl` — download events
- `progress.json` — per-category/page checkpoint for `--resume`

Status is **derived** from the last event type per `post_id`, not stored explicitly. `query_by_status()` reads the entire file into memory on every call.

## Key Constraints

- **`config/proxy.yaml` is gitignored** — must be provided by user (Clash format). Falls back to no-proxy if missing/Clash not running.
- **Only SS (Shadowsocks) proxy nodes** are loaded from Clash config; vmess/trojan/hysteria are silently ignored.
- **Anti-hotlinking bypass**: ZIP files on `ipo.ai-tag.cn` require a valid Referer from `ipoipo.cn/download/{post_id}.html`. The sequence is: visit download page → wait 0.5-1s → download with Referer header → validate Content-Type is not `text/html`.
- **Full crawl without limits takes 2+ hours** (3000+ pages across 38 categories). Always use `--max-pages` for testing.
- **`--category` flag is parsed but not fully wired** in all stages — known gap.
- **Multi-doc ZIPs**: if a ZIP contains multiple documents, they all get renamed to the same filename — later ones overwrite earlier ones.

## Testing

- 44 tests across 6 modules using `unittest` (pytest-compatible discovery).
- Tests use mocks — no network calls.
- Write tests for new functionality; ensure all pass before committing.

## Code Style

- Black formatting, Ruff linting (no config files — use defaults).
- No type-checking config; some type hints exist but are not enforced.

## Docs

- `docs/gotchas.md` — detailed known issues and edge cases
- `docs/changelog.md` — v2.0 redesign history (SQLite → JSONL migration)
- `docs/ipoipo-website-reference.md` — website structure reference
