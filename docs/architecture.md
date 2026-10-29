# Architecture: ipoipo Downloader v3

## Goals

Incremental discovery, recoverable download jobs, validated output, durable checkpoints, complete audit history, and safe repeat runs. The project deliberately prioritizes correctness over concurrency.

## Four stages

1. Category seed: ships a known mapping of 38 categories. This is a seed, not dynamic website discovery.
2. Listing: fetch category pages, parse metadata, upsert by numeric post_id, preserve category membership. Commit next_page ONLY after records from that page have been persisted.
3. URL resolution: claim pending resolve task from SQLite, parse allowed HTTPS ZIP URL, finish or explicitly fail/retry. No infinite pending loop.
4. Artifact acquisition: claim download task, stream into staging, verify ZIP and members, extract uniquely named documents, create SHA-256 manifest, atomically publish, commit artifact rows and successful status.

## Boundaries

- domain: immutable records and state contracts
- sources: website-specific parsing and navigation, no direct SQL writes
- pipeline: orchestration, bounded jobs, retries and recovery
- transport: HTTPS allowlist, explicit redirect validation, rate limiting
- artifacts: ZIP validation, secure extraction, manifests, filesystem publishing
- persistence: SQLite WAL transactional state and audit events
- observability: logs and run metrics

## Persistence

SQLite is the canonical source of truth for task status and audit events; JSONL can be exported for analysis. Transactional claim uses BEGIN IMMEDIATE and an owner/lease. Repeated report discovery does not reset finished work. Artifact publishing occurs before database completion. If a crash happens between the two operations, the next run reuses a verified manifest, so retries are idempotent.

## Multi-process considerations

Task claiming is safe across concurrent SQLite connections. Discovery currently assumes one orchestrator per category; running several full crawlers for the same category can overwrite checkpoints. Keep a single discovery coordinator, or introduce a distinct category lease before distributing crawling. Workers renew their leases during long downloads.

## Security

The client restricts targets to configured HTTPS hosts and checks each redirect. ZIPs are bounded by compressed size, uncompressed size, entry count and member size. Paths, symlinks, archive CRC and supported document signatures are validated. No execution of downloaded files. HTTP 401/403 is a terminal error; the system does not evade authorization barriers.

## Performance strategy

Keep one request stream per worker initially. Add measured parallelism only after state invariants and source rate policies are validated. Index queries use (stage,status,available_at). Audit event exports are explicit, not per-query full-file scans.

## v3.1 concurrency semantics

`category_leases(category_id PRIMARY KEY, owner, lease_until, updated_at)` is introduced in schema migration 0002. A listing producer claims its category using `BEGIN IMMEDIATE` before reading or updating the checkpoint. Lease expiry enables crash takeover; a heartbeat renews the lease during page requests. Every production checkpoint write checks owner and expiry in the same transaction. Another producer receives `busy_categories` rather than racing to advance pagination.

Task leases and category leases are separate. The offline legacy ZIP importer uses the validated artifact pipeline but deliberately has no logical downloaded-report task until a verified source identifier can be established.

Local Clash/Mihomo controller selection validates its reported choice. Optional egress observation is a separate HTTP request via the configured explicit proxy, not a claim that controller state equals network state.
