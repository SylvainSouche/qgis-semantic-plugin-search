"""Batched icon fetch orchestration (req-result-rows icon path).

Event discipline under test: one search produces at most one background job
and one batched GUI callback; each URL is fetched once per session; stale
batches are dropped; per-icon failures never reach the GUI thread.
"""

from pathlib import Path

from SemanticPluginSearch.Controllers.IconController import IconController
from SemanticPluginSearch.Data.AssetGateways import HttpIconGateway
from SemanticPluginSearch.Domain.Entities import PluginInfo, SearchResult
from tests.conftest import FakeIconGateway, InlineRunner, ManualRunner


def makeResult(pluginId: int, iconUrl: str = "") -> SearchResult:
    return SearchResult(
        info=PluginInfo(pluginId=pluginId, name=f"P{pluginId}", iconUrl=iconUrl),
        score=0.5,
    )


def test_one_batched_callback_per_result_batch():
    gateway = FakeIconGateway()
    controller = IconController(gateway, InlineRunner())
    batches = []
    controller.fetchFor(
        [makeResult(1, "https://x.test/a.png"), makeResult(2), makeResult(3, "https://x.test/c.png")],
        lambda batch: batches.append(batch),
    )
    # One callback, both icons, in a single delivery.
    assert len(batches) == 1
    assert sorted(batches[0]) == [(1, b"png:https://x.test/a.png"), (3, b"png:https://x.test/c.png")]


def test_urls_are_fetched_once_per_session():
    gateway = FakeIconGateway()
    controller = IconController(gateway, InlineRunner())
    results = [makeResult(1, "https://x.test/a.png")]
    batches = []
    controller.fetchFor(results, lambda batch: batches.append(batch))
    controller.fetchFor(results, lambda batch: batches.append(batch))
    assert batches != [] and len(batches) == 1, "second batch is fully served"
    assert gateway.fetched == ["https://x.test/a.png"]


def test_stale_batch_is_dropped_entirely():
    gateway = FakeIconGateway()
    runner = ManualRunner()
    controller = IconController(gateway, runner)
    first: list = []
    second: list = []
    controller.fetchFor([makeResult(1, "https://x.test/a.png")], lambda b: first.append(b))
    controller.fetchFor([makeResult(2, "https://x.test/b.png")], lambda b: second.append(b))
    runner.completeNext()  # batch one finishes after batch two started
    assert first == [], "stale batch must not reach the view"
    runner.completeNext()
    assert second == [[(2, b"png:https://x.test/b.png")]]


def test_per_icon_failures_are_skipped_not_raised():
    class FailingIconGateway:
        def fetchIcon(self, url: str) -> bytes:  # noqa: ANN001, ANN202
            if url.endswith("a.png"):
                raise RuntimeError("broken icon")
            return b"png"

    gateway = FailingIconGateway()
    controller = IconController(gateway, InlineRunner())
    batches = []
    controller.fetchFor(
        [makeResult(1, "https://x.test/a.png"), makeResult(2, "https://x.test/ok.png")],
        lambda batch: batches.append(batch),
    )
    assert batches == [[(2, b"png")]]


def test_gateway_caches_on_disk_and_memory(tmp_path: Path):
    calls = []

    def transport(url: str, maxBytes: int | None = None) -> bytes:  # noqa: ANN001, ANN202
        calls.append(url)
        return b"\x89PNG fake"

    gateway = HttpIconGateway(tmp_path / "Icons", transport=transport)
    url = "https://x.test/icon.png"
    first = gateway.fetchIcon(url)
    second = gateway.fetchIcon(url)
    assert first == second == b"\x89PNG fake"
    assert calls == [url], "second fetch must come from the cache"
    assert list(p.suffix for p in (tmp_path / "Icons").iterdir()) == [".png"]


def test_gateway_rejects_non_image_payload(tmp_path: Path):
    gateway = HttpIconGateway(
        tmp_path / "Icons",
        transport=lambda url, maxBytes=None: b"<html>404</html>",
    )
    try:
        gateway.fetchIcon("https://x.test/broken.png")
        raised = False
    except ValueError:
        raised = True
    assert raised
