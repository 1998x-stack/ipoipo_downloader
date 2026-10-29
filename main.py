"""Backward compatible script entrypoint for the v3 package CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ipoipo.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
