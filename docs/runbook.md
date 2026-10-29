# Operator runbook

## Setup

Requires Python 3.11+.

```bash
python -m pip install -e ".[dev,legacy]"
ipoipo --stage1 --data-dir data
ipoipo --full --category 85 --max-pages 2 --max-reports 5 --no-proxy
ipoipo --stats
```

## Core commands

- `--full`: sequential discovery -> URL resolve -> download; fails fast if the listing source is unavailable
- `--stage1`: initialize known categories
- `--stage2`: listing only
- `--stage3`: resolve eligible tasks
- `--stage4`: download eligible tasks
- `--resume`: continue incomplete category checkpoint, skip completed category
- `--incremental`: scan categories again from page 1, preserving finished reports
- `--retry`: reset permanently failed tasks manually
- `--max-pages`: maximum listing pages per category in this invocation
- `--max-reports`: global maximum download jobs in this invocation
- `--limit`: maximum URL resolution jobs in this invocation
- `--category 85`: target only one category
- `--import-legacy`: import old metadata without trusting old files
- `--export-events PATH`: export canonical SQLite audit events

## Operational principles

Use small `--max-pages` for smoke testing. Respect site policies and resource limits. A failed job may require a later run when its retry_wait becomes due. Back up the SQLite database together with downloaded files; SQLite WAL sidecars must be considered when backing up a live instance.

## CI

`ruff check src/ipoipo --select E4,E7,E9,F`
`python -m pytest tests -q`

Tests use synthetic HTML and ZIP fixtures; live browsing is deliberately excluded from CI.\nThe CI runs both the new v3 tests and the old legacy test modules.

## Not yet production-certified

Live website contract checks, multi-day soak tests, large-volume benchmarks, full static typing, versioned migrations beyond bootstrap, automatic source category discovery, and distributed discovery leases are future work.

## v3.1 operator actions

```bash
# Get counts from canonical SQLite even when launched outside the repo
bash scripts/stats.sh data

# Check a category checkpoint while preventing simultaneous listing producers
ipoipo --stage2 --category 85 --resume --max-pages 5

# Import up to 10 old archives without deleting the original files
ipoipo --extract --archive-dir data/downloads --max-reports 10

# Explicit local proxy state selection, no implicit retries via rotation
IPOIPO_PROXY_CONTROLLER_TOKEN="..." ipoipo --stats \
  --proxy-url http://127.0.0.1:7890 \
  --proxy-controller-url http://127.0.0.1:9090 \
  --proxy-group GLOBAL --proxy-node NODE_A
```

The timeout/expiry of a category lease is configured via `Settings.lease_seconds`.
Do not run multiple independent discovery coordinators without upgrading to v3.1; older deployments are not protected. A controller's selected node is not proof of egress IP unless an explicit diagnostic probe is run.
