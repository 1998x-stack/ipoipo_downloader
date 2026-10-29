import io
import json
import subprocess
import sys
import zipfile

from ipoipo.artifacts.local_import import import_local_archive, scan_old_archives
from ipoipo.artifacts.validator import ArtifactError
from ipoipo.settings import Settings
import pytest


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, contents in files.items():
            z.writestr(name, contents)
    return buf.getvalue()


def test_local_import_multiple_documents_does_not_mutate_original(tmp_path):
    legacy = tmp_path / "downloads" / "85_AI"
    legacy.mkdir(parents=True)
    archive = legacy / "report.zip"
    source = zip_bytes({"same.pdf": b"%PDF-1.4\ncontent", "more.txt": b"hello"})
    archive.write_bytes(source)
    settings = Settings(data_dir=tmp_path, keep_zip=False)
    first, docs = import_local_archive(settings, archive)
    assert first.is_file()
    assert len(docs) == 2
    assert {d.path.suffix for d in docs} == {".pdf", ".txt"}
    assert archive.read_bytes() == source
    assert (first.parent / "source.zip").exists() is False
    assert import_local_archive(settings, archive)[0] == first
    assert scan_old_archives(tmp_path / "downloads", category="85") == [archive]
    assert scan_old_archives(tmp_path / "downloads", category="79") == []


def test_invalid_archive_never_publishes(tmp_path):
    archive = tmp_path / "bad.zip"
    archive.write_bytes(zip_bytes({"../../escape.pdf": b"%PDF-1.4\ncontent"}))
    with pytest.raises(ArtifactError):
        import_local_archive(Settings(data_dir=tmp_path), archive)
    assert not list((tmp_path / "downloads-v3").rglob("manifest.json"))


def test_legacy_extract_cli_uses_safe_pipeline(tmp_path):
    old = tmp_path / "downloads" / "85_AI"
    old.mkdir(parents=True)
    (old / "ok.zip").write_bytes(zip_bytes({"good.pdf": b"%PDF-1.4\ncontent"}))
    cmd = [sys.executable, "-m", "ipoipo.cli", "--extract",
           "--data-dir", str(tmp_path), "--category", "85"]
    process = subprocess.run(cmd, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    data = json.loads(process.stdout)
    assert data["local_archive_import"]["imported"] == 1
    assert list((tmp_path / "downloads-v3" / "legacy-archives").rglob("manifest.json"))
