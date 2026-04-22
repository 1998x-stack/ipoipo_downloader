# ipoipo Downloader

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-44%20passing-brightgreen.svg)]()
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Automated pipeline for scraping and downloading IPO industry reports from [ipoipo.cn](https://ipoipo.cn). Features anti-hotlinking bypass, proxy rotation, resume capability, and structured JSONL storage.

## Features

- **4-Stage Pipeline** — Categories → Report Lists → Download URLs → ZIP Download
- **Parallel Execution** — Stages 2, 3, and 4 run concurrently with wait-check loops
- **Anti-Hotlinking Bypass** — Tengine CDN Referer ACL bypass via session management
- **Proxy Rotation** — Clash YAML parsing, node latency testing, auto-switch on failure
- **Resume Support** — Per-category and per-page checkpoint tracking via `progress.json`
- **JSONL Storage** — Append-only event log with state derivation (no SQLite dependency)
- **Smart Dedup** — Skips already-downloaded reports, validates file integrity
- **Auto Extraction** — Unzips reports and renames with `{YYYYMMDD}_{title}.{ext}` format
- **Structured Logging** — Colored console output + machine-parseable JSONL event log

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline (dry-run scale)
python main.py --full --max-pages 2 --max-reports 10

# Resume from last checkpoint
python main.py --full --resume
```

## Pipeline Stages

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Stage 1    │───▶│   Stage 2    │───▶│   Stage 3    │───▶│   Stage 4    │
│ Categories  │    │ Report Lists │    │  Download    │    │   Download   │
│             │    │              │    │   URLs       │    │   + Extract  │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  categories.jsonl    reports.jsonl      reports.jsonl      reports.jsonl
```

### Stage 1: Scrape Categories
Discovers all 38 report categories (TMT, AI, Finance, Education, etc.) and stores them in `categories.jsonl`.

### Stage 2: Scrape Report Lists
Paginates through each category's report listing, extracting post IDs, titles, thumbnails, and metadata. Supports `--max-pages` to limit depth.

### Stage 3: Extract Download URLs
Visits each report's download page, extracts the ZIP file URL from the HTML. Bypasses Tengine CDN anti-hotlinking by establishing session cookies first.

### Stage 4: Download & Extract
Downloads ZIP files with proper Referer headers, validates content type, extracts documents, and renames them with timestamp + title format.

## CLI Reference

### Pipeline Control

| Flag | Description |
|------|-------------|
| `--full` | Run all stages sequentially |
| `--stage1` | Stage 1 only: scrape categories |
| `--stage2` | Stage 2 only: scrape report lists |
| `--stage3` | Stage 3 only: extract download URLs |
| `--stage4` | Stage 4 only: download reports |
| `--retry` | Retry failed downloads |
| `--extract` | Extract downloaded ZIPs only |
| `--stats` | Show pipeline statistics |

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--max-pages N` | Max pages per category | Unlimited |
| `--max-reports N` | Max reports to process | Unlimited |
| `--limit N` | Limit for Stage 3 | 100 |
| `--category ID` | Filter by category ID | All |
| `--no-proxy` | Disable proxy | `false` |
| `--keep-zip` | Retain ZIP after extraction | `false` |
| `--resume` | Resume from last checkpoint | `false` |

### Examples

```bash
# Full pipeline with limits
python main.py --full --max-pages 5 --max-reports 50

# Download specific category
python main.py --stage4 --category 85 --max-reports 20

# Retry failed downloads
python main.py --retry --max-reports 10

# Run without proxy
python main.py --full --no-proxy

# Background execution
bash scripts/run.sh
```

## Architecture

### Module Structure

```
ipoipo_downloader/
├── main.py              # CLI entry point, parallel pipeline orchestration
├── scraper.py           # Stages 1-3: HTML parsing, event emission
├── downloader.py        # Stage 4: ZIP download, extraction, rename
├── storage.py           # JSONL storage: append, query, state derivation
├── logger.py            # Dual output: colored console + JSONL file
├── proxy.py             # Clash config parsing, node selection, auto-switch
├── config.py            # Centralized configuration
├── utils/
│   ├── headers.py       # Browser header generation
│   ├── sanitize.py      # Filename cleaning, timestamp extraction
│   └── helpers.py       # Retry decorator, jitter sleep, URL helpers
├── scripts/
│   ├── run.sh           # Background pipeline runner
│   ├── run_stage.sh     # Single stage runner
│   └── stats.sh         # JSONL stats summary
├── data/                # Runtime data (gitignored)
│   ├── categories.jsonl
│   ├── reports.jsonl
│   ├── downloads.jsonl
│   ├── progress.json
│   └── downloads/       # Downloaded files organized by category
└── logs/
    ├── events.jsonl     # Structured event log
    └── output.log       # Console output capture
```

### Storage Design

The system uses append-only JSONL files instead of a database. Each action appends an event:

```jsonl
{"type": "report_found", "post_id": "26028", "category_id": "85", "title": "...", "ts": "..."}
{"type": "url_found", "post_id": "26028", "download_url": "https://...", "ts": "..."}
{"type": "download_completed", "post_id": "26028", "file_path": "...", "file_size": 12345, "ts": "..."}
```

Status is derived from the last event per `post_id`:
- `report_found` → `pending`
- `url_found` → `ready`
- `download_completed` → `downloaded`
- `download_failed` → `failed`

### Anti-Hotlinking

ZIP files are hosted on `ipo.ai-tag.cn` (Alibaba Cloud CDN) with Referer ACL protection. The bypass works by:

1. Visiting `https://ipoipo.cn/download/{post_id}.html` to establish session cookies
2. Waiting 0.5-1s to simulate human behavior
3. Downloading the ZIP with `Referer: https://ipoipo.cn/download/{post_id}.html`
4. Validating `Content-Type` is not `text/html` (catches stealth 403s)

### Proxy Management

```
config/proxy.yaml (Clash format)
        │
        ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  Load Config      │────▶│  Test Nodes       │────▶│  Select Random    │
│  Parse SS nodes   │     │  TCP connect test │     │  Latency < 500ms  │
└───────────────────┘     └───────────────────┘     └───────────────────┘
                                                         │
                        ┌───────────────────┐            │
                        │  Switch on 403    │◀───────────┘
                        │  Mark node failed │
                        │  Clear cookies    │
                        └───────────────────┘
```

## Configuration

### Proxy Setup

1. Place your Clash config at `config/proxy.yaml`
2. Ensure Clash is running locally (default port 7890)
3. The system auto-detects the port from `mixed-port` in the config

```yaml
# config/proxy.yaml (example)
mixed-port: 7890
proxies:
  - name: "HK 01"
    type: ss
    server: example.com
    port: 12345
    cipher: aes-128-gcm
    password: "your-password"
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_PROXY` | Enable/disable proxy | `true` |

### Settings

All settings are in `config.py`:

```python
REQUEST_DELAY = (1, 3)        # Random delay between requests (seconds)
MAX_RETRIES = 3               # Max retry attempts per request
DOWNLOAD_TIMEOUT = 300        # Download timeout (seconds)
MIN_VALID_FILE_SIZE = 1024    # Minimum valid file size (bytes)
MAX_FILENAME_LENGTH = 200     # Maximum filename length
```

## File Organization

Downloaded files are organized by category with sanitized names:

```
data/downloads/
├── 85_人工智能AI行业/
│   ├── 20251222_中国人工智能发展报告_55页.pdf
│   ├── 20251220_AI行业趋势分析_38页.pdf
│   └── ...
├── 7_教育行业/
│   ├── 20251215_在线教育市场研究_42页.pdf
│   └── ...
└── 70_TMT行业/
    └── ...
```

Filename format: `{YYYYMMDD}_{sanitized_title}_{pages}页.{ext}`

## Logging

### Console Output
Real-time colored output with emoji indicators:

```
2026-04-22 08:00:00 [INFO ] main         Stage 2: Scraping category:85 人工智能AI行业
2026-04-22 08:00:01 [OK   ] main         report:26028 中国人工智能发展报告（55页）
2026-04-22 08:00:30 [WARN ] downloader   ⚠ 403 on post:26029, switching proxy...
2026-04-22 08:00:35 [OK   ] downloader   ✓ downloaded: 26029 (12.3 MB, 15.2s)
```

### Event Log
Structured JSONL for analysis:

```bash
# Count events by type
jq -r '.type' logs/events.jsonl | sort | uniq -c

# Find all failed downloads
jq -c 'select(.level == "error")' logs/events.jsonl

# Track a specific report
jq -c 'select(.post_id == "26028")' logs/events.jsonl
```

## Testing

```bash
# Run all tests
python -m unittest discover tests/ -v

# Run specific test module
python -m unittest tests/test_storage.py -v
```

Test coverage:
- `test_utils.py` — Headers, sanitization, helpers (15 tests)
- `test_logger.py` — Dual output logging (5 tests)
- `test_storage.py` — JSONL storage operations (11 tests)
- `test_proxy.py` — Proxy manager (5 tests)
- `test_scraper.py` — HTML parsing (3 tests)
- `test_downloader.py` — Download flow (4 tests)

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `403 Forbidden` on ZIP download | Missing Referer header | Ensure you're using the latest version |
| `Connection refused` on port 7890 | Clash not running | Start Clash or use `--no-proxy` |
| `unknown` folder in downloads | Missing `category_name` in storage | Run with `--resume` to backfill |
| Duplicate downloads | Storage/disk state mismatch | Run `python main.py --stats` to check |
| Slow scraping | Rate limiting | Increase `REQUEST_DELAY` in `config.py` |

### Debug Mode

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python main.py --stage2 --max-pages 1
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`python -m unittest discover tests/ -v`)
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ipoipo.cn](https://ipoipo.cn) — Source of IPO industry reports
- [Clash](https://github.com/Dreamacro/clash) — Proxy configuration format
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [requests](https://requests.readthedocs.io/) — HTTP client with session management
