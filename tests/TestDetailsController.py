"""Details orchestration: metadata now, readme in the background,
stale fetches dropped (t-inspect-tabs, req-two-tabs).
"""
from __future__ import annotations

from SemanticPluginSearch.Controllers.DetailsController import DetailsController
from tests.conftest import (
    FakeReadmeGateway,
    FakeView,
    InlineRunner,
    ManualRunner,
)
from SemanticPluginSearch.Domain.Entities import PluginInfo


def makeInfo(pluginId: int, name: str = "SomePlugin") -> PluginInfo:
    return PluginInfo(
        pluginId=pluginId,
        name=name,
        description="A fixture plugin",
        readmeUrl="https://example.test/readme.md",
    )


def test_metadata_shows_and_readme_arrives_in_background():
    view = FakeView()
    controller = DetailsController(FakeReadmeGateway(), InlineRunner())
    controller.showDetails(view, makeInfo(42))
    assert view.metadata and view.metadata[-1].name == "SomePlugin"
    assert view.readmes == [(42, "readme of SomePlugin")]
    assert view.placeholders, "a loading placeholder is shown first"


def test_readme_failure_shows_placeholder_not_exception():
    view = FakeView()
    gateway = FakeReadmeGateway()
    gateway.failures.add(7)
    controller = DetailsController(gateway, InlineRunner())
    controller.showDetails(view, makeInfo(7))
    assert view.readmes == []
    assert any("could not be loaded" in message for _, message in view.placeholders)


def test_no_readme_url_means_placeholder_without_fetch():
    view = FakeView()
    gateway = FakeReadmeGateway()
    controller = DetailsController(gateway, InlineRunner())
    info = PluginInfo(pluginId=1, name="NoReadme", description="")
    controller.showDetails(view, info)
    assert gateway.calls == []
    assert any("No readme" in message for _, message in view.placeholders)


def test_stale_readme_result_is_dropped():
    view = FakeView()
    runner = ManualRunner()
    controller = DetailsController(FakeReadmeGateway(), runner)
    controller.showDetails(view, makeInfo(1, "First"))
    controller.showDetails(view, makeInfo(2, "Second"))
    runner.completeNext()  # the fetch started for plugin 1 finishes late
    assert view.readmes == [], "the stale result must be dropped"
    assert controller.displayedPluginId() == 2
    runner.completeNext()  # the fetch for the current selection arrives
    assert view.readmes == [(2, "readme of Second")]
