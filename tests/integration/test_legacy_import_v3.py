import json

from ipoipo.persistence.legacy_import import import_legacy
from ipoipo.persistence.repository import Repository


def test_import_is_idempotent_and_does_not_trust_legacy_completed(tmp_path):
    (tmp_path / "categories.jsonl").write_text(
        json.dumps({"category_id":"85","category_name":"AI"},ensure_ascii=False) + "\n")
    entries = [
        {"type":"report_found","post_id":"101","category_id":"85","title":"AI report"},
        {"type":"url_found","post_id":"101","download_url":"https://ipo.ai-tag.cn/101.zip"},
        {"type":"download_completed","post_id":"101","file_path":"/unverified/101.pdf"},
    ]
    (tmp_path / "reports.jsonl").write_text(
        "\n".join(json.dumps(x,ensure_ascii=False) for x in entries),encoding="utf-8")
    repo = Repository(tmp_path / "new.db")
    try:
        first = import_legacy(tmp_path, repo)
        second = import_legacy(tmp_path, repo)
        assert first["reports_imported"] == second["reports_imported"] == 1
        assert repo.stats()["reports"] == 1
        assert repo.stats()["tasks"]["download:pending"] == 1
        assert first["legacy_files_verified"] == 0
    finally:
        repo.close()
