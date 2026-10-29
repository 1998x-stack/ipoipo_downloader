"""Bounded streaming ZIP extraction; each attachment keeps its actual file type."""
from pathlib import Path
import zipfile

from ipoipo.artifacts.naming import safe_filename
from ipoipo.artifacts.validator import (ArtifactError, DOCUMENT_SUFFIXES, verify_document,
                                         file_sha256)
from ipoipo.domain.models import Artifact
from ipoipo.settings import Settings


def extract_documents(archive_path: Path, destination: Path, settings: Settings) -> list[Artifact]:
    destination.mkdir(parents=True, exist_ok=True)
    artifacts: list[Artifact] = []
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or Path(member.filename).suffix.lower() not in DOCUMENT_SUFFIXES:
                continue
            suffix = Path(member.filename).suffix.lower()
            stem = safe_filename(Path(member.filename.replace("\\", "/")).stem)
            target = destination / f"{len(artifacts) + 1:03d}_{stem}{suffix}"
            # One file is streamed rather than loaded fully into RAM.
            with archive.open(member, "r") as source, target.open("xb") as sink:
                size = 0
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_member_bytes:
                        raise ArtifactError("ZIP member exceeded size limit")
                    sink.write(chunk)
            media_type = verify_document(target)
            artifacts.append(Artifact(target, file_sha256(target), target.stat().st_size, media_type))
    if not artifacts:
        raise ArtifactError("ZIP contained no supported documents")
    return artifacts
