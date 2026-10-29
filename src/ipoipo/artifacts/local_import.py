"""Offline migration of old ZIP archives using the same v3 validation pipeline.

The original files are NEVER deleted or modified; unverified archives never get
a manifest. These imports are stored separately from online report tasks.
"""
import os
import shutil
import tempfile
from pathlib import Path

from ipoipo.artifacts.extractor import extract_documents
from ipoipo.artifacts.manifest import write_manifest
from ipoipo.artifacts.validator import ArtifactError, file_sha256, validate_zip, verified_manifest
from ipoipo.domain.models import Artifact
from ipoipo.settings import Settings


def import_local_archive(settings: Settings, source: Path) -> tuple[Path, list[Artifact]]:
    source = Path(source)
    if source.is_symlink() or not source.is_file() or source.suffix.lower() != ".zip":
        raise ArtifactError("Local input must be a regular ZIP file, not a symlink")
    if source.stat().st_size > settings.max_archive_bytes:
        raise ArtifactError("Oversized local ZIP file")
    # Hash content to produce a deterministic, non-guessable archive identity.
    archive_sha = file_sha256(source)
    dest_root = settings.download_dir / "legacy-archives"
    target = dest_root / archive_sha[:24]
    prior = verified_manifest(target)
    if prior:
        return prior
    validate_zip(source, settings)
    dest_root.mkdir(parents=True, exist_ok=True)
    staging = dest_root / ".staging"
    staging.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=archive_sha[:12] + "-", dir=staging))
    try:
        archive_path = workspace / "source.zip"
        shutil.copyfile(source, archive_path)
        if file_sha256(archive_path) != archive_sha:
            raise ArtifactError("Source archive changed while being copied")
        validate_zip(archive_path, settings)
        docs = extract_documents(archive_path, workspace / "documents", settings)
        if not settings.keep_zip:
            archive_path.unlink()
        # No filesystem path or old, unverified report ID is treated as trusted identity.
        write_manifest(workspace, post_id=str(int(archive_sha[:16], 16)),
                       source_url="legacy-archive:sha256:" + archive_sha,
                       archive_sha256=archive_sha, artifacts=docs)
        if target.exists():
            quarantine = dest_root / ".quarantine"
            quarantine.mkdir(exist_ok=True)
            os.replace(target, quarantine / (archive_sha[:24] + "-" + workspace.name))
        os.replace(workspace, target)
        result = verified_manifest(target)
        if result is None:
            raise ArtifactError("Offline archive publication failed validation")
        return result
    finally:
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)


def scan_old_archives(root: Path, *, category: str | None = None) -> list[Path]:
    """Find only non-symlink ZIP files within a selected legacy archive tree."""
    root = Path(root)
    if not root.exists():
        return []
    if not root.is_dir() or root.is_symlink():
        raise ValueError("archive-dir must be a real directory")
    root_resolved = root.resolve()
    found = []
    for path in root.rglob("*.zip"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            path.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        if category is not None and not any(
            part.startswith(category + "_") for part in path.relative_to(root).parts[:-1]
        ):
            continue
        found.append(path)
    return sorted(found)
