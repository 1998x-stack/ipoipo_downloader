# ipoipo Downloader

IPO industry report scraper for ipoipo.cn. Downloads reports as PDF/Word/Excel files.

## Quick Start

```bash
pip install -r requirements.txt
python main.py --full --max-pages 2 --max-reports 10
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py --full` | Run all stages |
| `python main.py --stage1` | Scrape categories |
| `python main.py --stage2 --max-pages 5` | Scrape report lists |
| `python main.py --stage3 --limit 50` | Get download URLs |
| `python main.py --stage4 --max-reports 20` | Download reports |
| `python main.py --retry --max-reports 10` | Retry failed downloads |
| `python main.py --extract` | Extract ZIPs only |
| `python main.py --stats` | Show statistics |
| `python main.py --full --no-proxy` | Run without proxy |
| `python main.py --keep-zip` | Keep ZIP files after extraction |

## Architecture

Event-driven pipeline with JSONL storage:

```
main.py → Scraper (Stages 1-3) → Downloader (Stage 4)
                ↓                       ↓
          storage.py (JSONL)      storage.py (JSONL)
```

### Modules

| File | Responsibility |
|------|---------------|
| `config.py` | URLs, categories, settings |
| `scraper.py` | HTML scraping, event emission |
| `downloader.py` | ZIP download, extraction, rename |
| `storage.py` | JSONL append/query, state derivation |
| `logger.py` | Dual output (console + JSONL) |
| `proxy.py` | Clash config, node selection, auto-switch |
| `utils/` | Headers, filename sanitization, helpers |

## Proxy

Requires Clash running locally. Config in `config/proxy.yaml` (gitignored — provide your own).

## Anti-Hotlinking

ZIP files on `ipo.ai-tag.cn` require Referer from `ipoipo.cn`. The scraper visits the download page first, then downloads with correct Referer.

## File Organization

```
data/downloads/
├── 85_人工智能AI行业/
│   ├── 20251222_报告标题.pdf
│   └── ...
└── 7_教育行业/
    └── ...
```

## Logs

- Console: colored real-time output
- File: `logs/events.jsonl` (structured JSON for analysis)
