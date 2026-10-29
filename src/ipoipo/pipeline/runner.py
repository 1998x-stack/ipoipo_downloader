"""Four-stage reliable pipeline, with explicit errors and incremental checkpoints."""
import logging
import threading
import uuid
from typing import Any

from ipoipo.artifacts.downloader import ArtifactDownloader
from ipoipo.domain.states import Stage
from ipoipo.persistence.repository import Repository
from ipoipo.pipeline.recovery import recover
from ipoipo.pipeline.retry import with_retries
from ipoipo.pipeline.workers import WorkerResult, drain_stage
from ipoipo.settings import Settings
from ipoipo.sources.ipoipo_cn.categories import BASE_URL, CATEGORY_NAMES
from ipoipo.sources.ipoipo_cn.listing import ListingClient
from ipoipo.sources.ipoipo_cn.resolver import Resolver
from ipoipo.transport.http import HttpClient
from ipoipo.transport.proxy import ClashController, ProxyEndpoint, observe_egress_ip


class PipelineRunner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = Repository(settings.database_path)
        self.proxy_diagnostics: dict[str, str] = {}
        if settings.proxy_node and settings.proxy_group and settings.proxy_controller_url:
            controller = ClashController(
                settings.proxy_controller_url, token=settings.proxy_controller_token
            )
            try:
                self.proxy_diagnostics["selected_node"] = controller.select(
                    settings.proxy_group, settings.proxy_node
                )
            finally:
                controller.close()
        if settings.check_proxy_egress and settings.proxy_url:
            self.proxy_diagnostics["observed_egress_ip"] = observe_egress_ip(
                ProxyEndpoint(settings.proxy_url)
            )
        self.http = HttpClient(settings)
        self.listing = ListingClient(self.http)
        self.resolver = Resolver(self.http)
        self.artifacts = ArtifactDownloader(settings, self.http)
        self.log = logging.getLogger(__name__)

    def close(self) -> None:
        self.http.close()
        self.repository.close()

    def seed_categories(self) -> int:
        for category_id, name in CATEGORY_NAMES.items():
            self.repository.upsert_category(category_id, name, f"{BASE_URL}/tags-{category_id}.html")
        return len(CATEGORY_NAMES)

    def discover(self, *, category_id: str | None = None, max_pages: int | None = None,
                 resume: bool = False, incremental: bool = False) -> dict[str, int]:
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive")
        self.seed_categories()
        summary = {"new_reports": 0, "pages": 0, "categories": 0}
        categories = self.repository.categories(category_id)
        if not categories:
            raise ValueError(f"Unknown category {category_id}")
        summary["busy_categories"] = 0
        for category in categories:
            cid, name = category["category_id"], category["name"]
            owner = "crawl-" + uuid.uuid4().hex
            if not self.repository.acquire_category_lease(cid, owner, self.settings.lease_seconds):
                summary["busy_categories"] += 1
                self.log.info("Category %s claimed by another producer; skipping", cid)
                continue
            stop_heartbeat = threading.Event()

            def heartbeat() -> None:
                interval = max(0.5, min(30.0, self.settings.lease_seconds / 3))
                while not stop_heartbeat.wait(interval):
                    try:
                        self.repository.renew_category_lease(cid, owner, self.settings.lease_seconds)
                    except RuntimeError:
                        return

            thread = threading.Thread(target=heartbeat, name=f"crawl-lease-{cid}", daemon=True)
            thread.start()
            try:
                next_page, complete = self.repository.checkpoint(cid)
                if incremental or not resume:
                    next_page, complete = 1, False
                if resume and complete and not incremental:
                    continue
                page = next_page
                count = 0
                while max_pages is None or count < max_pages:
                    data = with_retries(lambda: self.listing.page(cid, name, page),
                                        self.settings.max_attempts)
                    if data.is_end:
                        self.repository.save_checkpoint(cid, 1, complete=True, owner=owner)
                        break
                    for report in data.reports:
                        summary["new_reports"] += int(self.repository.upsert_report(report))
                    page += 1
                    count += 1
                    summary["pages"] += 1
                    # Ownership and checkpoint write are validated in one transaction.
                    self.repository.save_checkpoint(cid, page, complete=False, owner=owner)
                summary["categories"] += 1
            finally:
                stop_heartbeat.set()
                thread.join(timeout=2)
                self.repository.release_category_lease(cid, owner)
        return summary

    def resolve_pending(self, *, limit: int | None = None,
                        category_id: str | None = None) -> WorkerResult:
        owner = "resolve-" + uuid.uuid4().hex[:12]

        def action(task):
            url = self.resolver.resolve(task.post_id)
            self.repository.resolved(task, url)

        return drain_stage(self.repository, Stage.RESOLVE, owner, action,
                           limit=limit, category_id=category_id,
                           lease_seconds=self.settings.lease_seconds)

    def download_ready(self, *, limit: int | None = None,
                       category_id: str | None = None) -> WorkerResult:
        owner = "download-" + uuid.uuid4().hex[:12]

        def action(task):
            report = self.repository.report(task.post_id)
            if not report or not report["download_url"]:
                raise ValueError("Download URL missing")
            referer = f"{BASE_URL}/download/{task.post_id}.html"
            manifest, documents = self.artifacts.obtain(
                task.post_id, report["download_url"], referer)
            self.repository.downloaded(task, documents, manifest)

        return drain_stage(self.repository, Stage.DOWNLOAD, owner, action,
                           limit=limit, category_id=category_id,
                           lease_seconds=self.settings.lease_seconds)

    def startup_recovery(self) -> dict[str, int]:
        return recover(self.repository, self.settings.download_dir)

    def run_full(self, *, category_id: str | None = None, max_pages: int | None = None,
                 limit: int | None = None, max_reports: int | None = None,
                 resume: bool = False, incremental: bool = False) -> dict[str, Any]:
        repaired = self.startup_recovery()
        discovered = self.discover(category_id=category_id, max_pages=max_pages,
                                   resume=resume, incremental=incremental)
        resolved = self.resolve_pending(limit=limit, category_id=category_id)
        downloaded = self.download_ready(limit=max_reports, category_id=category_id)
        return {"recovery": repaired, "discovery": discovered,
                "resolution": vars(resolved), "downloads": vars(downloaded),
                "stats": self.repository.stats()}
