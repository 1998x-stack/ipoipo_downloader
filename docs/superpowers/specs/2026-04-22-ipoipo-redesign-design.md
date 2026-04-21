# ipoipo Downloader — Redesign Spec

> Date: 2026-04-22 | Branch: redesign-jsonl-system | Status: Draft

## 1. Overview

Complete ground-up redesign of the ipoipo.cn report scraper. Replaces SQLite with JSONL storage, introduces structured dual-output logging, cleaner file organization, and domain-driven module architecture.

### Goals
- Replace SQLite with JSONL for git-friendly, simple storage
- Structured logging: human-readable console + machine-parseable JSON file
- Flat file organization by category with clean naming
- Domain-driven modules with clear separation of concerns
- Sequential execution with auto proxy-switch on failure

### Non-Goals
- No concurrent/multi-threaded downloads (keep it simple and safe)
- No web UI or API
- No database migration from old SQLite (fresh start)

---

## 2. Architecture

### File Structure
```
ipoipo_downloader/
├── main.py              # CLI entry point, argparse, pipeline orchestration
├── scraper.py           # Stage 1-3: categories, report lists, download URLs
├── downloader.py        # Stage 4: ZIP download, extract, rename
├── storage.py           # JSONL read/write, dedup, query helpers
├── logger.py            # Dual output: colored console + structured JSON file
├── proxy.py             # Clash YAML parsing, node testing, auto-switch
├── config.py            # All settings: URLs, delays, categories, paths
├── .gitignore           # data/, logs/, __pycache__/, .env, *.pyc
├── README.md            # Setup, usage, architecture overview
├── config/
│   └── proxy.yaml       # Clash proxy configuration (SS nodes)
├── scripts/
│   ├── run.sh           # Full pipeline: nohup python main.py --full
│   ├── run_stage.sh     # Run single stage: bash run_stage.sh 2 --max-pages 5
│   └── stats.sh         # Quick stats: jq-based JSONL summary
├── utils/
│   ├── __init__.py
│   ├── headers.py       # Browser header generation, rotation
│   ├── sanitize.py      # Filename cleaning, timestamp extraction
│   └── helpers.py       # Common: sleep_with_jitter, retry decorator, url helpers
├── docs/
│   └── ipoipo-website-reference.md
├── data/                # Runtime data (gitignored)
│   ├── categories.jsonl
│   ├── reports.jsonl
│   ├── downloads.jsonl
│   └── downloads/       # Downloaded files
└── logs/
    ├── app.log          # Human-readable console-style log
    └── events.jsonl     # Structured JSON event log
```

### Module Responsibilities

| Module | Does | Does NOT |
|--------|------|----------|
| `main.py` | CLI args, pipeline sequencing, cleanup | No scraping/downloading logic |
| `scraper.py` | HTTP requests, HTML parsing, yields events | No file I/O, no DB writes |
| `downloader.py` | ZIP download (with Referer bypass), extract, rename | No HTML parsing, no URL discovery |
| `storage.py` | JSONL append, read, dedup by ID, query by field | No HTTP, no parsing |
| `logger.py` | Console (colored) + JSON file output | No business logic |
| `proxy.py` | Clash config parse, node test, switch on failure | No HTTP requests directly |
| `config.py` | Constants, category map, path setup | No runtime logic |
| `utils/headers.py` | Browser header generation | No HTTP requests |
| `utils/sanitize.py` | Filename cleaning, timestamp extraction | No file I/O |
| `utils/helpers.py` | Retry decorator, jitter sleep, URL helpers | No business logic |

### Event Flow
```
scraper.yield_category()   → storage.append("categories", event)
scraper.yield_report()     → storage.append("reports", event)
scraper.yield_download_url() → storage.append("reports", event)
downloader.yield_download()  → storage.append("downloads", event)
```

---

## 3. Storage Design (JSONL)

### 3.1 File Schemas

**`data/categories.jsonl`** — one line per category
```json
{"type": "category", "category_id": "85", "category_name": "人工智能AI行业", "url": "https://ipoipo.cn/tags-85.html", "ts": "2026-04-22T10:00:00"}
```

**`data/reports.jsonl`** — append-only event log, latest event per `post_id` wins
```json
{"type": "report_found", "post_id": "26028", "category_id": "85", "title": "...", "detail_url": "...", "thumbnail_url": "...", "view_count": 44, "publish_date": "2025-12-22", "ts": "..."}
{"type": "url_found", "post_id": "26028", "download_url": "https://ipo.ai-tag.cn/...", "ts": "..."}
{"type": "download_started", "post_id": "26028", "ts": "..."}
{"type": "download_completed", "post_id": "26028", "file_path": "...", "file_size": 1234567, "ts": "..."}
{"type": "download_failed", "post_id": "26028", "error": "403 Forbidden", "ts": "..."}
```

**`data/downloads.jsonl`** — one line per download attempt (audit trail)
```json
{"post_id": "26028", "zip_url": "https://ipo.ai-tag.cn/...", "status": "success", "file_path": "...", "file_size": 1234567, "attempts": 1, "proxy_node": "香港 01", "duration_sec": 12.5, "ts": "..."}
{"post_id": "26028", "zip_url": "...", "status": "failed", "error": "403", "attempts": 2, "proxy_node": "香港 02", "duration_sec": 5.2, "ts": "..."}
```

### 3.2 Status Derivation

Reports have no explicit `status` field. Status is derived from the last event type for a given `post_id`:

| Last Event Type | Derived Status |
|----------------|----------------|
| `report_found` | `pending` — needs download URL |
| `url_found` | `ready` — has URL, ready to download |
| `download_started` | `downloading` — in progress |
| `download_completed` | `downloaded` — complete |
| `download_failed` | `failed` — needs retry |

### 3.3 Dedup & Query

- **Dedup**: In-memory `set` of seen IDs per file type. Rebuilt from existing JSONL on startup.
- **Query "pending reports"**: Load `reports.jsonl`, group by `post_id`, keep last event. Filter where last event is `report_found`.
- **Query "ready to download"**: Last event is `url_found` with no subsequent `download_completed`.
- **Query "failed"**: Last event is `download_failed`.
- **Retry behavior**: `--retry` appends a new `url_found` event for each failed report, resetting derived status to `ready`
- **Stats**: Count events by type, group by `category_id`.

### 3.4 Storage API
```python
storage = Storage("data/")

# Append
storage.append("reports", {"type": "report_found", "post_id": "26028", ...})

# Get last state for a report
state = storage.get_state("reports", "26028")
# → {"type": "url_found", "download_url": "...", "ts": "..."}

# Query all reports with a given derived status
reports = storage.query_by_status("reports", "pending")

# Get stats
stats = storage.get_stats()
# → {"total_categories": 39, "total_reports": 1234, "by_status": {...}}
```

---

## 4. Logging System

### 4.1 Dual Output

| Output | Format | File | Purpose |
|--------|--------|------|---------|
| Console | Colored text | stdout | Real-time monitoring |
| File | Structured JSON | `logs/events.jsonl` | Post-run analysis, metrics |

### 4.2 Console Format
```
2026-04-22 10:00:00 [INFO]  scraper    Stage 1: scraping categories...
2026-04-22 10:00:01 [OK]    scraper    ✓ category:85 人工智能AI行业
2026-04-22 10:00:05 [INFO]  scraper    Stage 2: scraping reports for category:85
2026-04-22 10:00:06 [OK]    scraper    ✓ report:26028 中国地方公共数据开放利用报告
2026-04-22 10:00:30 [WARN]  downloader ⚠ 403 on post:26028, switching proxy...
2026-04-22 10:00:35 [OK]    downloader ✓ downloaded: 26028 (12.3 MB, 15.2s)
2026-04-22 10:00:35 [ERROR] downloader ✗ failed: 26029 — connection timeout
```

### 4.3 JSON Event Log (`logs/events.jsonl`)
```json
{"ts": "2026-04-22T10:00:00", "level": "info", "module": "scraper", "event": "stage_start", "stage": 1, "msg": "scraping categories"}
{"ts": "2026-04-22T10:00:01", "level": "ok", "module": "scraper", "event": "category_found", "category_id": "85", "category_name": "人工智能AI行业", "url": "https://ipoipo.cn/tags-85.html"}
{"ts": "2026-04-22T10:00:30", "level": "warn", "module": "downloader", "event": "proxy_switch", "post_id": "26028", "reason": "403", "old_node": "香港 01", "new_node": "香港 02"}
{"ts": "2026-04-22T10:00:35", "level": "ok", "module": "downloader", "event": "download_completed", "post_id": "26028", "file_size": 12900000, "duration_sec": 15.2}
```

### 4.4 Logger API
```python
from logger import get_logger

log = get_logger("scraper")
log.info("Stage 1: scraping categories", stage=1)
log.ok("category found", category_id="85", category_name="人工智能AI")
log.warn("403 on download", post_id="26028", reason="hotlink_denied")
log.error("download failed", post_id="26029", error="timeout")
```

- `log.info()` → blue `[INFO]` on console
- `log.ok()` → green `[OK]` on console
- `log.warn()` → yellow `[WARN]` on console
- `log.error()` → red `[ERROR]` on console

All kwargs become JSON fields in the file output. Console uses a compact template.

---

## 5. File System

### 5.1 Directory Layout
```
data/downloads/
├── 85_人工智能AI行业/
│   ├── 20251222_中国地方公共数据开放利用报告.pdf
│   ├── 20251220_AI行业发展趋势分析.pdf
│   └── 20251218_生成式AI应用白皮书.pdf
├── 7_教育行业/
│   ├── 20251215_在线教育市场研究报告.pdf
│   └── 20251210_K12教育数字化趋势.docx
└── 34_经济报告/
    └── ...
```

### 5.2 Naming Rules
- **Folder**: `{category_id}_{category_name}/`
- **File**: `{YYYYMMDD}_{sanitized_title}.{ext}`
- **Timestamp source** (in priority order):
  1. Extracted from ZIP filename (`202512021157134086066.zip` → `20251202`)
  2. Report's `publish_date` from scraping
  3. Current date as fallback
- **ZIP files**: Deleted after successful extraction (default). `--keep-zip` flag to retain.

### 5.3 Sanitization
- Remove: `<>:"/\|?*【】（）《》""''：；，。！？`
- Replace with `_`
- Collapse multiple `_` into one
- Strip leading/trailing `_` and spaces
- Max length: 200 chars (including extension)

### 5.4 Disk Dedup
- Before downloading, check if a file matching `{YYYYMMDD}_{title}` pattern exists in the category folder
- If exists and size > 1KB → skip
- If exists but size ≤ 1KB → overwrite (corrupted)

---

## 6. Proxy & Anti-Hotlinking

### 6.1 Proxy Management
- Load from `config/proxy.yaml` (Clash format, SS nodes)
- Parse `mixed-port` for local proxy URL (`http://127.0.0.1:{port}`)
- Test nodes via TCP connect on startup
- Select random node with latency < 500ms for each session; fall back to fastest if none qualify
- **Auto-switch**: On 403 or 2 consecutive failures → mark node failed, select new random node, clear cookies, retry

### 6.2 Anti-Hotlinking (Tengine CDN)
- ZIP files hosted on `ipo.ai-tag.cn`, protected by Referer ACL
- Must visit `https://ipoipo.cn/download/{post_id}.html` first
- Download ZIP with `Referer: https://ipoipo.cn/download/{post_id}.html`
- Use `requests.Session()` to maintain cookies
- Wait ~1s between page visit and ZIP download (simulate human behavior)

### 6.3 Browser Headers
- Full Chrome 120 macOS fingerprint
- `Sec-Fetch-Site: cross-site` for ZIP downloads (different domain)
- Headers generated by `utils/headers.py`, rotated if needed

---

## 7. Pipeline Stages

```
Stage 1: Categories
  → Iterate CATEGORY_NAMES, emit category events → storage

Stage 2: Report Lists
  → For each category, scrape tags-{id}.html and tags-{id}_{N}.html
  → Parse .wapost.card elements, emit report_found events → storage

Stage 3: Download URLs
  → For each pending report, visit download/{post_id}.html
  → Extract ZIP URL, emit url_found events → storage

Stage 4: Download
  → For each ready report, visit download page → download ZIP with Referer
  → Extract ZIP, rename docs, emit download_completed/failed → storage
  → Delete ZIP (default)
```

### CLI Commands
```bash
python main.py --full --max-pages 2 --max-reports 10
python main.py --stage1
python main.py --stage2 --max-pages 5
python main.py --stage3 --limit 50
python main.py --stage4 --max-reports 20
python main.py --stage4 --category 85 --max-reports 10
python main.py --retry --max-reports 10   # reset failed reports to ready, re-download
python main.py --stats
python main.py --full --no-proxy
python main.py --keep-zip
python main.py --extract --max-reports 20   # extract ZIPs without re-downloading
```

### Shell Scripts
```bash
bash scripts/run.sh              # nohup python main.py --full > logs/output.log 2>&1 &
bash scripts/run_stage.sh 2 5    # run stage 2 with --max-pages 5
bash scripts/stats.sh            # jq-based summary of JSONL files
```

---

## 8. Error Handling

| Error | Action |
|-------|--------|
| 403 on ZIP download | Switch proxy node, clear cookies, retry (max 3 attempts) |
| 2 consecutive failures (any) | Switch proxy node |
| Invalid ZIP file | Skip extraction, keep ZIP for inspection, log error |
| Network timeout | Retry with exponential backoff (1s, 2s, 4s), max 3 attempts total |
| Empty page (no reports) | Stop pagination for that category |
| KeyboardInterrupt | Graceful shutdown, flush storage, log partial stats |

---

## 9. Dependencies

```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
PyYAML>=6.0
```

No loguru, no SQLite, no pytest (use unittest like before).

---

## 10. .gitignore

```
__pycache__/
*.pyc
*.pyo
data/
logs/
.env
*.egg-info/
dist/
build/
```
