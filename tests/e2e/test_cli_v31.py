import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def make_zip(path: Path, member: str, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(member, content)
    path.write_bytes(stream.getvalue())


def test_main_entrypoint_safe_extraction(tmp_path):
    source = tmp_path / "downloads" / "85_AI" / "bad.zip"
    make_zip(source, "../../escape.pdf", b"%PDF-1.4\nx")
    cmd = [sys.executable, str(ROOT / "main.py"), "--extract",
           "--archive-dir", str(tmp_path / "downloads"), "--data-dir", str(tmp_path)]
    output = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert output.returncode == 1
    result = json.loads(output.stdout)
    assert result["local_archive_import"]["failed"] == 1
    assert source.is_file()
    assert not (tmp_path / "escape.pdf").exists()


def test_stats_shell_uses_v3_sqlite(tmp_path):
    cmd = ["bash", str(ROOT / "scripts/stats.sh"), str(tmp_path)]
    output = subprocess.run(cmd, cwd="/", capture_output=True, text=True, check=True)
    data = json.loads(output.stdout)
    assert data["stats"]["reports"] == 0
    assert data["stats"]["artifacts"] == 0
    assert "tasks" in data["stats"]
