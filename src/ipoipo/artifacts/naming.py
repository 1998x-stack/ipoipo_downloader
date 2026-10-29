"""Stable, collision-free output naming based on post_id and attachment index."""
import re
import unicodedata


def safe_filename(name: str, maximum: int = 120) -> str:
    value = unicodedata.normalize("NFKC", name)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value[:maximum].rstrip(" ._") or "unnamed")


def safe_post_id(value: str) -> str:
    if not value.isdigit() or len(value) > 20:
        raise ValueError("post_id must be a short numeric identifier")
    return value
