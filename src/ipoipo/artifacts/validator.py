"""File signature, manifest and archive structure validation."""
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from ipoipo.domain.models import Artifact
from ipoipo.settings import Settings

DOCUMENT_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"})
MIME = {".pdf":"application/pdf", ".doc":"application/msword",
        ".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt":"application/vnd.ms-powerpoint",
        ".pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xls":"application/vnd.ms-excel",
        ".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt":"text/plain"}
OLE = bytes.fromhex("D0CF11E0A1B11AE1")


class ArtifactError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def verify_document(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in DOCUMENT_SUFFIXES or path.stat().st_size == 0:
        raise ArtifactError(f"Unsupported or empty document: {path.name}")
    with path.open("rb") as handle:
        header = handle.read(16)
    if ext == ".pdf" and not header.startswith(b"%PDF-"):
        raise ArtifactError(f"Invalid PDF signature: {path.name}")
    if ext in {".doc", ".ppt", ".xls"} and not header.startswith(OLE):
        raise ArtifactError(f"Invalid OLE document: {path.name}")
    if ext in {".docx", ".pptx", ".xlsx"} and not zipfile.is_zipfile(path):
        raise ArtifactError(f"Invalid OOXML document: {path.name}")
    return MIME[ext]


def validate_zip(path: Path, settings: Settings) -> list[zipfile.ZipInfo]:
    if path.stat().st_size > settings.max_archive_bytes or not zipfile.is_zipfile(path):
        raise ArtifactError("Invalid or oversized ZIP file")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > settings.max_archive_entries:
            raise ArtifactError("ZIP entry count exceeds limit")
        total = 0
        for member in members:
            segments = member.filename.replace("\\", "/").split("/")
            if (member.filename.startswith(("/", "\\")) or
                    any(part in {"..", ""} for part in segments[:-1]) or
                    ".." in segments or ":" in member.filename):
                raise ArtifactError("Unsafe ZIP member path")
            mode = (member.external_attr >> 16)
            if stat.S_ISLNK(mode):
                raise ArtifactError("ZIP symlinks are not allowed")
            if member.flag_bits & 1:
                raise ArtifactError("Encrypted ZIP entries are not supported")
            total += member.file_size
            if member.file_size > settings.max_member_bytes or total > settings.max_uncompressed_bytes:
                raise ArtifactError("ZIP extraction size budget exceeded")
        bad = archive.testzip()
        if bad:
            raise ArtifactError(f"ZIP CRC verification failed: {bad}")
    return members


def verified_manifest(directory: Path) -> tuple[Path, list[Artifact]] | None:
    manifest = directory / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        rows = data["documents"]
        if not rows:
            return None
        artifacts = []
        for row in rows:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                return None
            path = (directory / relative).resolve()
            path.relative_to(directory.resolve())
            if not path.is_file() or path.stat().st_size != row["size"]:
                return None
            if file_sha256(path) != row["sha256"]:
                return None
            artifacts.append(Artifact(path, row["sha256"], row["size"], row["media_type"]))
        return manifest, artifacts
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
