"""Compatibility launcher for the canonical v3.1 CLI.

All commands, including --extract, route to validated src/ipoipo modules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ipoipo.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
