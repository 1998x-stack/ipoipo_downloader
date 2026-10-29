import json
import subprocess
import sys


def test_cli_stage1_and_stats(tmp_path):
    cmd = [sys.executable, "-m", "ipoipo.cli", "--stage1", "--stats", "--data-dir", str(tmp_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    result = json.loads(proc.stdout)
    assert result["seed_categories"] == 38
    assert result["stats"]["categories"] == 38
