# Worker state machine

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running: claim
    retry_wait --> running: claim when due
    running --> succeeded: validated result committed
    running --> retry_wait: retryable error, budget remaining
    running --> failed: terminal error or exhausted budget
    failed --> pending: manual retry
```

## Guarantees

- Atomic claim increments attempts, records owner and lease expiry.
- A second worker cannot claim an unexpired running task.
- Ownership is checked before completing or failing a task.
- A heartbeat renews leases during long operations.
- Crash recovery moves expired running tasks to retry_wait or failed.
- No worker loops over future-dated retries, so unresolved links cannot cause infinite busy loops.
- A completed report is never reset to pending by rediscovery.
- Manual retry explicitly resets budget; it never runs implicitly on terminal errors.

## HTTP error classification

Connection errors, timeouts, 429 and 5xx are retryable. 401, 403, 404, 410, untrusted URLs, bad file signatures and rejected ZIP entries are terminal. Site HTML selector changes raise ParseError rather than being interpreted as the end of a category.

## Paging

Checkpoint next_page is updated after every successful page. Completed categories have (next_page=1, complete=true). --resume continues unfinished categories; --incremental intentionally starts again at page 1 and upsert preserves existing work.

## Category discovery lease (v3.1)

Category ownership is independent of resolve/download tasks. Owner A acquires category C; owner B sees it busy; A saves checkpoints only while the lease is live. A crashed producer loses its expired lease to B, and its subsequent checkpoint writes are fenced out. The lease is always released in a `finally` block on normal completion. Audit events `category_claimed` and `category_released` are recorded in SQLite.
