# ipoipo Downloader v3.1

Reliable, incremental and auditable acquisition of industry research reports published through **ipoipo.cn**.

> **Status:** v3.1 stabilization in review. Use an authorized source and follow the website's terms and rate limits. The software does not bypass authorization controls.

## What changed

- Four explicit stages with incremental discovery and durable page checkpoints
- Transactional SQLite WAL task queue, atomic worker claim and heartbeat lease
- Finite URL resolution retries and classified HTTP failures
- Bounded ZIP download, CRC and path safety checks, real attachment types
- Collision-free multi-document extraction and SHA-256 artifact manifests
- Atomic publication, crash recovery and manifest reconciliation
- Canonical SQLite events with JSONL export
- Offline unit, integration, E2E and property tests under Python 3.11/3.12 CI
- Legacy JSONL metadata import, without assuming old downloads are verified

## Quick start

```bash
python -m pip install -e ".[dev,legacy]"
ipoipo --stage1
ipoipo --full --category 85 --max-pages 2 --max-reports 5 --no-proxy
ipoipo --stats
ipoipo --full --category 85 --incremental --max-pages 2 --max-reports 5
```

The older `python main.py --full --category 85 ...` command forwards to the v3 CLI. The original top-level Python files are retained for historical reference and selected legacy utilities; new business logic lives in `src/ipoipo/`.

## Commands

| Option | Behavior |
| --- | --- |
| `--full` | Stages 1 to 4, sequentially |
| `--stage1` | Seed categories |
| `--stage2` | Fetch report listings |
| `--stage3` | Resolve report download URLs |
| `--stage4` | Download and validate assets |
| `--resume` | Resume incomplete category checkpoints |
| `--incremental` | Revisit category lists from page one |
| `--retry` | Requeue terminal failures manually |
| `--category 85` | Limit listing and task processing to category 85 |
| `--max-pages 2` | Page budget per category |
| `--limit 10` | URL resolution budget |
| `--max-reports 5` | Download budget per invocation |
| `--data-dir PATH` | State and artifact storage root |
| `--proxy-url URL` | Explicit local proxy (optional) |
| `--no-proxy` | Direct connection |
| `--keep-zip` | Keep verified original archive |
| `--import-legacy` | Import metadata from old JSONL |
| `--export-events PATH` | Export JSONL audit records |

## Architecture

```text
src/ipoipo/
  domain/          models, state contracts, audit event schema
  sources/ipoipo_cn/  category seed, HTML parser, pagination, ZIP link resolution
  pipeline/        runner, workers, retry, scheduler, recovery
  transport/       HTTP access policy, optional proxy endpoint, rate limit
  artifacts/       streaming transfer, ZIP safety, extraction, manifest
  persistence/     SQLite WAL repository, legacy import, JSONL export
  observability/   application logging, metrics
```

The SQLite store manages current state. A succeeded download requires a verified `manifest.json` and physical documents. Re-discovering a report does not cause a second download.

## Tests

```bash
python -m pip install -e ".[dev]"
ruff check src/ipoipo --select E4,E7,E9,F
python -m pytest tests -q
```

## Design and operations

Read [Architecture](docs/architecture.md), [Data Contracts](docs/data-contracts.md), [State Machine](docs/state-machine.md), [Recovery](docs/recovery.md), and [Operator Runbook](docs/runbook.md).

## Important limitations

- Stage 1 currently seeds known categories; true site-wide category discovery is not yet implemented.
- Each invocation processes currently eligible tasks. Deferred retries require a later run; the scheduler module is available to an integrating service.
- Running multiple independent listing coordinators against the same category is not supported.
- Live source compatibility and long-running production behavior have not yet been validated.
- Legacy completed downloads are not automatically trusted as valid v3 artifacts.

MIT License.

## v3.1 Reliability hardening

- **Cross-process listing coordination**: SQLite category leases protect pagination; stale leases can be recovered and a lost owner cannot write its checkpoint.
- **Explicit local proxy control**: an authorized local Clash/Mihomo controller may select a requested node; the reported selection is verified. No automatic node switching on 401/403/429.
- **Optional external egress observation**: `--check-proxy-egress` contacts `api.ipify.org` *through the configured proxy*. This sends the proxy's observed public IP to that service and must be explicitly enabled. A selected node alone is not proof of a changed external IP.
- **Safe legacy ZIP extraction**: `python main.py --extract` and `ipoipo --extract` now run the same bounded ZIP checks and manifest validation. Original archives remain unchanged and verified imports live in `data/downloads-v3/legacy-archives/<sha256-prefix>/`.
- **Canonical stats**: `bash scripts/stats.sh [DATA_DIR]` invokes `main.py --stats` against SQLite, rather than counting JSONL lines.

### Optional proxy selection and diagnosis

```bash
export IPOIPO_PROXY_CONTROLLER_TOKEN="<controller-api-token>"
ipoipo --stats --proxy-url http://127.0.0.1:7890 \
  --proxy-controller-url http://127.0.0.1:9090 \
  --proxy-group GLOBAL --proxy-node "NODE_A"
ipoipo --stats --proxy-url http://127.0.0.1:7890 --check-proxy-egress
```

The controller endpoint must be bound to loopback. Never use node selection to circumvent source authorization or rate restrictions.

### Migrate old ZIPs without redownloading

```bash
ipoipo --extract --archive-dir data/downloads --data-dir data --max-reports 10
python main.py --extract --category 85 --max-reports 10
```

Archive imports are catalogued by content hash, not assumed to be valid downloaded report tasks. Damaged archives produce errors and a nonzero CLI exit code. The original ZIP files are preserved even when `--keep-zip` is not set; that flag only controls the copy retained with the verified output.
