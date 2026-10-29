"""Download to staging, verify ZIP, safely extract, then atomically publish."""
import os
import shutil
import tempfile
from pathlib import Path

import requests

from ipoipo.artifacts.extractor import extract_documents
from ipoipo.artifacts.manifest import write_manifest
from ipoipo.artifacts.naming import safe_post_id
from ipoipo.artifacts.validator import ArtifactError, file_sha256, validate_zip, verified_manifest
from ipoipo.domain.models import Artifact
from ipoipo.settings import Settings
from ipoipo.transport.http import FetchError, HttpClient


class ArtifactDownloader:
    def __init__(self, settings: Settings, http: HttpClient):
        self.settings = settings
        self.http = http

    def obtain(self, post_id: str, zip_url: str, referer: str) -> tuple[Path, list[Artifact]]:
        post_id = safe_post_id(post_id)
        root = self.settings.download_dir
        root.mkdir(parents=True, exist_ok=True)
        target = root / post_id
        existing = verified_manifest(target)
        if existing:
            return existing

        staging_root = root / ".staging"
        staging_root.mkdir(exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=post_id + "-", dir=staging_root))
        try:
            archive_path = workspace / "source.zip"
            response = self.http.get(zip_url, referer=referer,
                                     stream=True, timeout=self.settings.download_timeout)
            try:
                ctype = response.headers.get("Content-Type", "").lower()
                if "text/html" in ctype:
                    raise ArtifactError("Server returned HTML instead of archive")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.settings.max_archive_bytes:
                    raise ArtifactError("Archive exceeds download size budget")
                size = 0
                with archive_path.open("xb") as sink:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > self.settings.max_archive_bytes:
                            raise ArtifactError("Download exceeded size budget")
                        sink.write(chunk)
                    sink.flush()
                    os.fsync(sink.fileno())
            except requests.RequestException as exc:
                raise FetchError(f"Incomplete download: {exc}") from exc
            finally:
                response.close()
            validate_zip(archive_path, self.settings)
            documents_dir = workspace / "documents"
            artifacts = extract_documents(archive_path, documents_dir, self.settings)
            archive_hash = file_sha256(archive_path)
            if not self.settings.keep_zip:
                archive_path.unlink()
            write_manifest(workspace, post_id=post_id, source_url=zip_url,
                           archive_sha256=archive_hash, artifacts=artifacts)
            if target.exists():
                # Do not overwrite a corrupt/incomplete prior result without preserving it.
                quarantine = root / ".quarantine"
                quarantine.mkdir(exist_ok=True)
                backup = quarantine / (post_id + "-" + workspace.name)
                os.replace(target, backup)
            os.replace(workspace, target)
            verified = verified_manifest(target)
            if not verified:
                raise ArtifactError("Published directory failed manifest verification")
            return verified
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
