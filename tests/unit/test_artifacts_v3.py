import io
import json
import zipfile
from pathlib import Path

import pytest

from ipoipo.artifacts.downloader import ArtifactDownloader
from ipoipo.artifacts.validator import ArtifactError, validate_zip, verified_manifest
from ipoipo.settings import Settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {"Content-Type": "application/zip", "Content-Length": str(len(payload))}
        self.closed = False

    def iter_content(self, chunk_size=1024):
        for offset in range(0, len(self.payload), chunk_size):
            yield self.payload[offset:offset + chunk_size]

    def close(self):
        self.closed = True


class FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


def archive_with(**files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, payload in files.items():
            z.writestr(name, payload)
    return stream.getvalue()


def test_multiple_documents_never_overwrite(tmp_path):
    binary = archive_with(**{"research.pdf": b"%PDF-1.4\nhello",
                             "attachment.txt": b"extra material"})
    http = FakeHTTP(binary)
    settings = Settings(data_dir=tmp_path, min_delay_seconds=0)
    downloader = ArtifactDownloader(settings, http)
    manifest, artifacts = downloader.obtain("123", "https://ipo.ai-tag.cn/a.zip",
                                             "https://ipoipo.cn/download/123.html")
    assert manifest.is_file()
    assert len(artifacts) == 2
    assert {a.path.suffix for a in artifacts} == {".pdf", ".txt"}
    assert len({a.path.name for a in artifacts}) == 2
    assert verified_manifest(settings.download_dir / "123") is not None
    assert downloader.obtain("123", "https://ipo.ai-tag.cn/a.zip",
                             "https://ipoipo.cn/download/123.html")[0] == manifest
    assert http.calls == 1


def test_fake_pdf_is_rejected_without_manifest(tmp_path):
    binary = archive_with(**{"research.pdf": b"not a pdf"})
    settings = Settings(data_dir=tmp_path, min_delay_seconds=0)
    with pytest.raises(ArtifactError):
        ArtifactDownloader(settings, FakeHTTP(binary)).obtain(
            "123", "https://ipo.ai-tag.cn/a.zip", "https://ipoipo.cn/download/123.html")
    assert not (settings.download_dir / "123" / "manifest.json").exists()


def test_zip_slip_rejected(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_bytes(archive_with(**{"../../escape.pdf": b"%PDF-1.4\nhi"}))
    with pytest.raises(ArtifactError):
        validate_zip(path, Settings(data_dir=tmp_path))


def test_archive_exceeds_uncompressed_budget(tmp_path):
    path = tmp_path / "huge.zip"
    path.write_bytes(archive_with(**{"huge.pdf": b"%PDF" + b"X" * 1024}))
    with pytest.raises(ArtifactError):
        validate_zip(path, Settings(data_dir=tmp_path, max_uncompressed_bytes=100))
