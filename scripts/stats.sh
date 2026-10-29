#!/usr/bin/env bash
# Print canonical v3 SQLite statistics; callable from any working directory.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-$ROOT/data}"
cd "$ROOT"
exec python3 main.py --stats --data-dir "$DATA_DIR"
