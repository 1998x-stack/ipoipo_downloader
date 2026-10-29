import threading
import time

import pytest

from ipoipo.domain.models import Report
from ipoipo.pipeline.runner import PipelineRunner
from ipoipo.persistence.repository import Repository
from ipoipo.settings import Settings
from ipoipo.sources.base import ListingPage
from ipoipo.transport.http import FetchError


def _report():
    return Report("123", "research", "85", "AI", "https://ipoipo.cn/post/123.html")


def test_busy_category_is_skipped_without_network(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0))
    second = Repository(runner.settings.database_path)
    try:
        runner.seed_categories()
        assert second.acquire_category_lease("85", "elsewhere", 120)
        runner.listing.page = lambda *args: pytest.fail("A busy category must not be fetched")
        summary = runner.discover(category_id="85", max_pages=1)
        assert summary["busy_categories"] == 1
        assert summary["pages"] == 0
        assert second.release_category_lease("85", "elsewhere")
    finally:
        second.close()
        runner.close()


def test_fail_after_page_does_not_reset_checkpoint(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, min_delay_seconds=0, max_attempts=1))
    requested = []

    def page(cid, name, number):
        requested.append(number)
        if number == 1:
            return ListingPage([_report()])
        if number == 2:
            raise FetchError("timeout", retryable=True)
        return ListingPage([], is_end=True)

    runner.listing.page = page
    try:
        with pytest.raises(FetchError):
            runner.discover(category_id="85", max_pages=3)
        assert runner.repository.checkpoint("85") == (2, False)
        runner.listing.page = lambda cid, name, number: ListingPage([], is_end=True)
        assert runner.discover(category_id="85", resume=True)["categories"] == 1
        assert runner.repository.checkpoint("85") == (1, True)
    finally:
        runner.close()


def test_category_heartbeat_renews_while_fetch_is_blocked(tmp_path):
    runner = PipelineRunner(Settings(data_dir=tmp_path, lease_seconds=1, min_delay_seconds=0))
    competing = Repository(runner.settings.database_path)
    entered = threading.Event()
    release = threading.Event()

    def slow_page(cid, name, number):
        entered.set()
        release.wait(timeout=3)
        return ListingPage([], is_end=True)

    runner.listing.page = slow_page
    outcome = []

    def run():
        try:
            outcome.append(runner.discover(category_id="85", max_pages=1))
        except Exception as error:
            outcome.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(2)
        time.sleep(1.35)
        assert not competing.acquire_category_lease("85", "intruder", 1)
    finally:
        release.set()
        thread.join(timeout=5)
        competing.close()
        runner.close()
    assert not thread.is_alive()
    assert outcome and isinstance(outcome[0], dict)
