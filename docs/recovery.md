# Recovery and legacy migration

## Restart

`ipoipo --full --resume --category 85 --max-pages 5 --max-reports 10`

Before processing, recovery examines expired worker leases and checks manifests of succeeded downloads. An invalid or missing manifest requeues the download. Orphaned staging directories are not authoritative and may be safely removed when no worker is active.

## Legacy JSONL

1. Make a backup of data/categories.jsonl, reports.jsonl and the existing download directory.
2. Run `ipoipo --import-legacy --data-dir data`.
3. Verify `ipoipo --stats --data-dir data`.
4. Run selected stages with `--stage3` and `--stage4` or `--full --resume`.
5. Use `--export-events data/events-v3.jsonl` for audit extraction.

Import retains report metadata and validated download URLs but deliberately does not declare old files complete; legacy filenames and old JSONL completion events do not provide verified v3 manifests.

## Failure recovery

- Network timeout: retry_wait with exponential backoff; run again after available_at or use a periodic scheduler.
- Permanent 403/404: failed; review permission or source state rather than switching proxies.
- ZIP corruption: failed with reason; inspect source.
- Crash while streaming: uncommitted staging directory may remain, but no false completion.
- Crash after filesystem commit before database commit: verified manifest is reused on next attempt.
- Lost final file: recovery detects mismatch and requeues download.
- Multi-process scheduling: use one listing producer per category, though downloaded task claims are transactionally exclusive.

## v3.1 category lease recovery

If a category producer crashes, its lease expires after the configured TTL. A new producer can acquire the same category and resume from the last committed next_page. An old producer that wakes up cannot update the checkpoint because `save_checkpoint(owner=...)` checks current ownership and expiry. A busy category is skipped and counted explicitly.

A completed category checkpoint is never manually reset during an active category lease. Report and task UPSERT operations are idempotent to tolerate page re-fetches after crashes.

## Offline legacy archive migration

`ipoipo --extract --archive-dir data/downloads` walks existing ZIPs, rejects archive symlinks, validates ZIP safety and document signatures, hashes and stages documents, publishes immutable manifests, and records success/failure audit events in SQLite. It does **not** delete source archives or incorrectly mark an old JSONL download status as verified.

## Proxy operational boundaries

To make an authorized controller selection, supply a loopback-only controller URL and a specific group/node. Verify a reported selection through the API; optionally observe the actual public exit IP through the configured proxy using `--check-proxy-egress`. IP-echo verification uses a third-party service and is opt-in. An HTTP 403 remains a terminal source response, not a trigger to change nodes.
