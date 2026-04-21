"""Filename sanitization and timestamp extraction."""
import re
from datetime import datetime
from pathlib import Path


ILLEGAL_CHARS = r'[<>:"/\\|?*【】（）《》""''：；，。！？\[\]]'


def clean_filename(name: str, max_length: int = 200) -> str:
    """Clean a filename, preserving extension."""
    path = Path(name)
    stem = path.stem
    ext = path.suffix

    stem = re.sub(ILLEGAL_CHARS, "_", stem)
    stem = stem.replace("（", "_").replace("）", "_")
    stem = stem.replace("【", "_").replace("】", "_")
    stem = re.sub(r"[_\s.]+", "_", stem)
    stem = stem.strip("_. ")

    if not stem:
        stem = "unnamed"

    max_stem = max_length - len(ext)
    if len(stem) > max_stem:
        stem = stem[:max_stem]

    return stem + ext


def clean_foldername(name: str) -> str:
    """Clean a folder name (stricter than filename)."""
    name = re.sub(ILLEGAL_CHARS, "_", name)
    name = name.replace("（", "_").replace("）", "_")
    name = name.replace("【", "_").replace("】", "_")
    name = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_ ")
    return name or "unnamed"


def extract_timestamp_from_zip(filename: str) -> str:
    """Extract YYYYMMDD from ZIP filename like 202512021157134086066.zip."""
    patterns = [
        r"^(\d{8})",
        r"(\d{8})_",
        r"_(\d{8})",
        r"(\d{14})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            ts = match.group(1)[:8]
            try:
                datetime.strptime(ts, "%Y%m%d")
                return ts
            except ValueError:
                continue
    return datetime.now().strftime("%Y%m%d")


def generate_doc_filename(zip_filename: str, report_title: str, publish_date: str = None) -> str:
    """Generate final document filename: YYYYMMDD_sanitized_title.ext."""
    ts = extract_timestamp_from_zip(zip_filename)
    ext = Path(zip_filename).suffix.replace(".zip", "")
    if not ext:
        ext = ".pdf"  # default

    clean_title = clean_filename(report_title)
    clean_title = clean_title.replace(".", "_").replace(" ", "")
    clean_title = clean_title.strip()

    return f"{ts}_{clean_title}{ext}"
