# ipoipo Downloader — Gotchas & Known Issues

> Generated from live run observations + code review. Last updated: 2026-04-22

---

## 1. Runtime Gotchas

### 1.1 Full crawl takes hours without `--max-pages`

**Symptom:** `python main.py --full` scrapes every page of all 38 categories. Category 70 (TMT行业) alone has 53+ pages. Total estimated: 3000+ pages × 2-3s delay = 2+ hours.

**Fix:** Always use `--max-pages` for testing:
```bash
python main.py --full --max-pages 2 --max-reports 10
```

### 1.2 Proxy config must exist at `config/proxy.yaml`

**Symptom:** `FileNotFoundError` if `config/proxy.yaml` doesn't exist. The file is gitignored for security.

**Fix:** Provide your own Clash config:
```bash
cp /path/to/your/clash.yaml config/proxy.yaml
# Or run without proxy:
python main.py --full --no-proxy
```

### 1.3 `USE_PROXY` is env-driven but defaults to `true`

**Symptom:** If Clash isn't running, proxy init fails and falls back to no-proxy — but with an error log. Users without proxies see confusing error messages.

**Fix:** Set `USE_PROXY=false` in environment:
```bash
USE_PROXY=false python main.py --full
```

### 1.4 `--category` flag accepted but not wired

**Symptom:** `python main.py --stage4 --category 85` accepts the arg but doesn't filter by category. The argument is parsed but never used in `main.py`.

**Status:** Known gap — reserved for future implementation.

---

## 2. Anti-Hotlinking Gotchas

### 2.1 ZIP download requires Referer from `ipoipo.cn`

**Root cause:** Tengine CDN on `ipo.ai-tag.cn` uses Referer ACL whitelist.

**Required sequence:**
1. Visit `https://ipoipo.cn/download/{post_id}.html` (establishes session)
2. Wait ~0.5-1s (simulate human behavior)
3. Download ZIP with `Referer: https://ipoipo.cn/download/{post_id}.html`

**If Referer is wrong:** 403 Forbidden with `X-Tengine-Error` header.
**If Referer is empty:** 403 Forbidden.
**If Referer is non-ipoipo domain:** 403 Forbidden.

### 2.2 Content-Type check catches HTML error pages

**Symptom:** If the download returns HTML instead of ZIP (stealth 403), the downloader checks `Content-Type` and rejects it.

**Code:** `downloader.py:56-58`
```python
if "text/html" in content_type.lower() and zip_url.endswith(".zip"):
    return False, 0
```

### 2.3 Proxy switch clears cookies

**Why:** New proxy node may need fresh session. Cookies from old node are invalid.

**Impact:** After proxy switch, the next download page visit must re-establish session. This adds ~1-2s overhead per switch.

---

## 3. Storage Gotchas

### 3.1 JSONL is append-only — files grow unbounded

**Symptom:** `reports.jsonl` accumulates one line per event. A report that goes through `report_found → url_found → download_completed` has 3 lines. After thousands of reports, the file can be large.

**Impact:** `query_by_status` reads the entire file into memory on every call. For 10K+ reports, this is fine (~few MB). For 100K+, consider compaction.

**No built-in compaction yet.**

### 3.2 Status is derived, not explicit

**How it works:** Status is derived from the last event type per `post_id`:
- `report_found` → `pending`
- `url_found` → `ready`
- `download_completed` → `downloaded`
- `download_failed` → `failed`

**Gotcha:** If you manually edit a JSONL file, you must ensure event ordering is correct. The last event for a `post_id` wins.

### 3.3 `_read_lines` is a private method used externally

**Code:** `scraper.py:141` calls `self.storage._read_lines("categories")`.

**Risk:** This couples Scraper to Storage internals. If Storage's internal API changes, Scraper breaks.

**Better:** Add a public `get_categories()` method to Storage.

---

## 4. File System Gotchas

### 4.1 Filename sanitization is aggressive

**Removed chars:** `<>:"/\|?*【】（）《》""''：；，。！？`

**Impact:** Some report titles lose meaningful punctuation. E.g., `报告【测试】（重要）` → `报告_测试__重要_`.

### 4.2 Duplicate filenames get no suffix

**Current behavior:** If two reports have the same date and similar titles, the second download overwrites the first (if size > 1KB check passes).

**Risk:** Low in practice — post_ids are unique, but titles can collide.

### 4.3 ZIP extraction renames ALL document files

**Behavior:** Every `.pdf`, `.docx`, `.pptx`, `.xlsx` in the ZIP gets renamed to `{YYYYMMDD}_{report_title}.{ext}`. If a ZIP contains multiple documents, they all get the same name — later ones overwrite earlier ones.

**Risk:** Medium. Most IPO report ZIPs contain a single document, but multi-doc ZIPs would lose files.

---

## 5. Proxy Gotchas

### 5.1 Only SS (Shadowsocks) nodes are loaded

**Code:** `proxy.py:38` — only `type == "ss"` proxies are parsed.

**Impact:** If your Clash config contains `vmess`, `trojan`, `hysteria` nodes, they're silently ignored.

### 5.2 `fail_count` has no recovery

**Behavior:** Once a node's `fail_count` reaches 3, it's permanently excluded from `select_random()`. No cooldown or reset.

**Impact:** If a node has a temporary outage, it's dead for the entire session. Restart the process to reset.

### 5.3 Node testing uses TCP connect, not HTTP health check

**Behavior:** `test_node()` does `socket.connect(server, port)` — only verifies the port is open, not that the proxy forwards traffic correctly.

**Impact:** A node could accept TCP connections but fail to proxy HTTP. False positives in node testing.

---

## 6. Logging Gotchas

### 6.1 Console output includes ANSI codes in redirected output

**Symptom:** When running with `nohup` or redirecting to file, ANSI color codes are still emitted. The output log contains raw escape sequences like `\033[34m`.

**Fix:** Detect if stdout is a TTY and skip colors for file output. Not yet implemented.

### 6.2 JSONL event log grows with every log call

**Behavior:** Every `log.info()`, `log.ok()`, etc. appends a line to `logs/events.jsonl`.

**Impact:** For long runs, this file can grow large. No rotation or truncation.

---

## 7. Scraper Gotchas

### 7.1 Pagination stops on empty page, not on 404

**Behavior:** `scrape_category()` stops when a page returns zero report cards. It does NOT check for HTTP 404.

**Risk:** If the website returns a valid HTML page with no cards (e.g., "no results" message), scraping stops correctly. But if the website returns an error page that happens to contain a `.wapost.card` div with different structure, parsing may produce garbage data.

### 7.2 `extract_zip_url` has 4 fallback methods

**Order:**
1. `href` ends with `.zip`
2. Style contains `font-size.*color`
3. Link text contains `.zip`
4. Regex match `http...zip` in raw HTML

**Risk:** If the website changes its HTML structure, methods 1-3 may fail. Method 4 (regex) is the most resilient but may match non-download links.

---

## 8. Downloader Gotchas

### 8.1 Consecutive failure counter resets after proxy switch

**Fixed in this branch:** Previously, `_consecutive_failures` was not reset after a successful proxy switch, causing immediate re-switch on the next failure.

### 8.2 `extract_downloaded_zips` uses ZIP filename as title fallback

**Behavior:** When extracting ZIPs without storage data, it uses the ZIP filename stem as the report title. This produces suboptimal filenames.

**Fix:** It now queries storage for the report title first.

### 8.3 Download dedup uses partial filename match

**Code:** `cat_dir.glob(f"{doc_pattern[:20]}*")` — matches first 20 chars of the expected filename.

**Risk:** Two reports with the same date and similar title prefixes could match the same existing file.
