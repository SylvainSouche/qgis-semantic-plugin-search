"""Icon fetch orchestration and the icon gateway cache
(req-result-rows icon path)."""

from pathlib import Path

from SemanticPluginSearch.Controllers.IconController import IconController
from SemanticPluginSearch.Data.AssetGateways import HttpIconGateway
from SemanticPluginSearch.Domain.Entities import PluginInfo, SearchResult
from tests.conftest import InlineRunner


class FakeIconGateway:
    def __init__(self) -> None:
        self.fetched: list[str] = []

    def fetchIcon(self, url: str) -> bytes:
        self.fetched.append(url)
        return b"png:" + url.encode()


def makeResult(pluginId: int, iconUrl: str = "") -> SearchResult:
    return SearchResult(
        info=PluginInfo(pluginId=pluginId, name=f"P{pluginId}", iconUrl=iconUrl),
        score=0.5,
    )


def test_fetches_only_plugins_with_icon_url():
    fetched = []
    controller = IconController(FakeIconGateway(), InlineRunner())
    controller.fetchFor(
        [makeResult(1, "https://x.test/a.png"), makeResult(2), makeResult(3, "https://x.test/c.png")],
        lambda pluginId, payload: fetched.append((pluginId, payload)),
    )
    assert sorted(pluginId for pluginId, _ in fetched) == [1, 3]
    assert fetched[0][1] == b"png:https://x.test/a.png"


def test_gateway_caches_on_disk_and_memory(tmp_path: Path):
    calls = []

    def transport(url: str) -> bytes:
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
    gateway = HttpIconGateway(tmp_path / "Icons", transport=lambda url: b"<html>404</html>")
    try:
        gateway.fetchIcon("https://x.test/broken.png")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_stale_icon_callback_is_ignored_by_the_view_contract():
    # The controller marshals per plugin id; the view drops unknown ids
    # (covered in the real view by _showIcon). Here: the id travels intact.
    seen = []
    controller = IconController(FakeIconGateway(), InlineRunner())
    controller.fetchFor([makeResult(7, "https://x.test/seven.png")],
                        lambda pluginId, payload: seen.append(pluginId))
    assert seen == [7]
