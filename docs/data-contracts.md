# Data contracts (v3)

## Report identity

A numeric post_id identifies a report within the currently supported ipoipo.cn source. Each report can belong to many categories, stored in report_categories. Extending to another site requires a composite identity (source, post_id) schema migration.

## Task

Unique key (post_id, stage). Stage is resolve or download. Status is pending, running, retry_wait, succeeded, or failed. A task has a nonnegative attempt count, retry budget, owner, expiration, next eligible time and last error.

## Artifact layout

data/downloads-v3/{post_id}/
- manifest.json
- documents/001_{original_stem}.{original_ext}
- documents/002_{original_stem}.{original_ext}
- source.zip (only when --keep-zip)

Output names are collision-free within a report. Extensions are based on actual archive members, never derived from the ZIP suffix. The manifest records relative paths, sha256, byte size, media type, source URL and archive hash.

## Completion invariant

download:succeeded => manifest exists AND contains at least one supported file AND every listed file matches its recorded size and hash. Completion is written only after publication and verification. Next run reconciles missing/corrupt manifests.

## Audit event fields

events(id, ts, type, post_id, stage, details JSON). Important event types: report_discovered, task_claimed, task_failed, url_resolved, download_completed, lease_recovered, artifact_reconciliation_failed, legacy_link_imported, manual_retry.

## Legacy import

--import-legacy reads categories.jsonl and reports.jsonl. Existing download_completed lines are NOT trusted as verified v3 files. Source ZIP URLs are validated against an HTTPS host allowlist. Imported reports and links are deduplicated, with unresolved tasks preserved.
