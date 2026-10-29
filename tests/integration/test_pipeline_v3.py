import io
import zipfile
from pathlib import Path

from ipoipo.pipeline.runner import PipelineRunner
from ipoipo.settings import Settings


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HTML = (FIXTURES / "category_page.html").read_text(encoding="utf-8")
DOWNLOAD_HTML = (FIXTURES / "download_page.html").read_text(encoding="utf-8")
EMPTY_HTML = (FIXTURES / "empty_page.html").read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.headers = {"Content-Type": "application/zip"}
    def iter_content(self, chunk_size):
        yield self.data
    def close(self):
        pass


def test_full_pipeline_and_incremental_no_redownload(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("report.pdf", b"%PDF-1.4\nvalid document")
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    counts = {"zip": 0, "listing": 0}

    def html_response(url, **kwargs):
        if "/tags-85.html" in url:
            counts["listing"] += 1
            return HTML
        if "/tags-85_2.html" in url:
            return EMPTY_HTML
        if "/download/26028.html" in url:
            return DOWNLOAD_HTML
        raise AssertionError(url)

    def stream_response(url, **kwargs):
        counts["zip"] += 1
        return FakeResponse(stream.getvalue())

    runner.http.get_html = html_response
    runner.http.get = stream_response
    try:
        first = runner.run_full(category_id="85")
        assert first["discovery"]["new_reports"] == 1
        assert first["downloads"]["succeeded"] == 1
        assert first["stats"]["artifacts"] == 1
        assert counts["zip"] == 1
        assert runner.repository.checkpoint("85") == (1, True)
        second = runner.run_full(category_id="85", incremental=True)
        assert second["discovery"]["new_reports"] == 0
        assert second["downloads"]["succeeded"] == 0
        assert counts["zip"] == 1
        assert runner.repository.stats()["tasks"]["download:succeeded"] == 1
    finally:
        runner.close()


def test_missing_artifact_requeued_on_next_run(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("report.pdf", b"%PDF-1.4\nvalid document")
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    runner.http.get_html = lambda url, **kw: (
        HTML if "/tags-85.html" in url else
        DOWNLOAD_HTML
        if "/download/" in url else "<html></html>")
    runner.http.get = lambda *a, **kw: FakeResponse(stream.getvalue())
    try:
        runner.run_full(category_id="85", max_pages=1)
        manifest = runner.settings.download_dir / "26028" / "manifest.json"
        manifest.unlink()
        repair = runner.startup_recovery()
        assert repair["requeued_invalid_artifacts"] == 1
        assert runner.repository.stats()["tasks"]["download:pending"] == 1
        assert runner.download_ready().succeeded == 1
    finally:
        runner.close()
