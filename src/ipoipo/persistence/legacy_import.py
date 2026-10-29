"""Idempotent import of legacy JSONL metadata. Unverified old files are NEVER marked complete."""
import json
from pathlib import Path
from typing import Any

from ipoipo.domain.models import Report
from ipoipo.persistence.repository import Repository
from ipoipo.sources.ipoipo_cn.categories import BASE_URL, CATEGORY_NAMES
from ipoipo.transport.http import FetchError, validate_url


def _records(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                yield record
        except json.JSONDecodeError:
            continue


def import_legacy(directory: Path, repository: Repository) -> dict[str, int]:
    """Import legacy categories and report links; force re-verification of downloaded assets.

    Old downloads.jsonl and download_completed events do not certify a validated
    manifest, so they are not treated as successful in v3.
    """
    for cid, name in CATEGORY_NAMES.items():
        repository.upsert_category(cid, name, f"{BASE_URL}/tags-{cid}.html")
    categories: dict[str, str] = dict(CATEGORY_NAMES)
    for event in _records(directory / "categories.jsonl"):
        cid = str(event.get("category_id", ""))
        if not cid.isdigit():
            continue
        name = str(event.get("category_name") or categories.get(cid) or "unknown")
        categories[cid] = name
        repository.upsert_category(cid, name, f"{BASE_URL}/tags-{cid}.html")

    reports: dict[str, dict[str, Any]] = {}
    urls: dict[str, str] = {}
    for event in _records(directory / "reports.jsonl"):
        pid = str(event.get("post_id", ""))
        if not pid.isdigit():
            continue
        if event.get("type") == "report_found":
            snapshot = reports.setdefault(pid, {})
            snapshot.update({k: v for k, v in event.items() if v is not None})
        elif event.get("type") == "url_found":
            candidate = str(event.get("download_url") or "")
            try:
                urls[pid] = validate_url(candidate, ("ipoipo.cn", "ipo.ai-tag.cn"))
            except FetchError:
                continue

    imported = 0
    recovered_links = 0
    for pid, data in reports.items():
        cid = str(data.get("category_id") or "0")
        if cid not in categories:
            categories[cid] = str(data.get("category_name") or "unknown")
            repository.upsert_category(cid, categories[cid], f"{BASE_URL}/tags-{cid}.html")
        repository.upsert_report(Report(
            post_id=pid, title=str(data.get("title") or f"report-{pid}"),
            category_id=cid, category_name=categories[cid],
            detail_url=f"{BASE_URL}/post/{pid}.html",
            publish_date=str(data.get("publish_date") or ""),
            thumbnail_url=str(data.get("thumbnail_url") or ""),
            description=str(data.get("description") or ""),
            view_count=int(data.get("view_count") or 0)))
        imported += 1
        if pid in urls:
            with repository.db.transaction() as c:
                c.execute("UPDATE reports SET download_url=? WHERE post_id=?", (urls[pid], pid))
                c.execute("""UPDATE tasks SET status='succeeded',owner=NULL,lease_until=NULL
                           WHERE post_id=? AND stage='resolve' AND status!='succeeded'""", (pid,))
                c.execute("""INSERT OR IGNORE INTO tasks(post_id,stage,updated_at)
                           VALUES(?,'download',strftime('%s','now'))""", (pid,))
                repository._event(c, "legacy_link_imported", pid, "resolve")
            recovered_links += 1
    return {"reports_imported": imported, "links_imported": recovered_links,
            "legacy_files_verified": 0}
