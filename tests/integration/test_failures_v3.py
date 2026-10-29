"""Failure-injection regressions for terminal URL resolution and download states."""
import io
import zipfile

from ipoipo.domain.models import Report
from ipoipo.persistence.repository import Repository
from ipoipo.pipeline.runner import PipelineRunner
from ipoipo.settings import Settings


def test_bad_zip_url_is_terminal_and_stage_ends(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    try:
        runner.seed_categories()
        runner.repository.upsert_report(Report(
            "1", "A", "85", "AI", "https://ipoipo.cn/post/1.html"))
        runner.http.get_html = lambda url, **kw: "<html>No ZIP download available</html>"
        outcome = runner.resolve_pending(limit=10, category_id="85")
        assert outcome.failed == 1
        assert outcome.attempted == 1
        assert runner.resolve_pending(limit=10, category_id="85").attempted == 0
        assert runner.repository.stats()["tasks"]["resolve:failed"] == 1
    finally:
        runner.close()


def test_invalid_archive_never_completed(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    try:
        runner.seed_categories()
        runner.repository.upsert_report(Report(
            "2", "B", "85", "AI", "https://ipoipo.cn/post/2.html"))
        job = runner.repository.claim("resolve", "url-worker")[0]
        runner.repository.resolved(job, "https://ipo.ai-tag.cn/2.zip")

        class InvalidResponse:
            headers = {"Content-Type": "application/zip"}
            def iter_content(self, chunk_size):
                yield b"invalid content, not a zip"
            def close(self):
                pass

        runner.http.get = lambda *a, **kw: InvalidResponse()
        outcome = runner.download_ready(limit=5)
        assert outcome.failed == 1
        assert not (runner.settings.download_dir / "2" / "manifest.json").exists()
        assert "download:succeeded" not in runner.repository.stats()["tasks"]
    finally:
        runner.close()


def test_global_download_budget(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    try:
        runner.seed_categories()
        for pid in ("1", "2"):
            runner.repository.upsert_report(Report(
                pid, "R"+pid, "85", "AI", f"https://ipoipo.cn/post/{pid}.html"))
            job = runner.repository.claim("resolve", "url-worker")[0]
            runner.repository.resolved(job, f"https://ipo.ai-tag.cn/{job.post_id}.zip")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("research.pdf", b"%PDF-1.4\ncontent")
        class Response:
            headers = {"Content-Type": "application/zip"}
            def iter_content(self, chunk_size):
                yield buffer.getvalue()
            def close(self):
                pass
        runner.http.get = lambda *a, **kw: Response()
        result = runner.download_ready(limit=1)
        assert result.attempted == 1
        assert runner.repository.stats()["tasks"]["download:pending"] == 1
    finally:
        runner.close()
