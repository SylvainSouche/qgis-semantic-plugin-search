"""Search and action controllers: results to the view, actions always
delegated to the manager gateway (t-actions-delegate, nreq-no-own-install).
"""
from __future__ import annotations

import pytest

from SemanticPluginSearch.Controllers.ActionController import ActionController
from SemanticPluginSearch.Controllers.SearchController import SearchController
from SemanticPluginSearch.Domain.Entities import ActionStates, PluginInfo, SearchResult
from SemanticPluginSearch.Domain.SearchEngine import SearchService
from tests.conftest import FakePluginManagerGateway, FakeReporter, FakeView


class StubSearchService:
    """Ranks nothing; returns canned results so views can be driven."""

    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def search(self, store, text, limit: int = 30) -> list[SearchResult]:  # noqa: ANN001
        self.calls.append(text)
        return self.results


def makeInfo(pluginId: int, name: str) -> PluginInfo:
    return PluginInfo(pluginId=pluginId, name=name, description="fixture")


# ------------------------------------------------------------------ search


def test_search_pushes_results_to_the_view():
    view = FakeView()
    service = StubSearchService([SearchResult(makeInfo(1, "A"), 0.9)])
    controller = SearchController(engine=None, searchService=service, reporter=FakeReporter())
    controller.store = object()
    controller.search(view, "parcel digitizing")
    assert view.results == service.results
    assert service.calls == ["parcel digitizing"]
    assert view.statuses, "a status line accompanies the results"


def test_search_without_store_is_reported_not_crashing():
    view = FakeView()
    controller = SearchController(
        engine=None, searchService=StubSearchService([]), reporter=FakeReporter()
    )
    controller.search(view, "anything")
    assert view.results == []
    assert view.cleared == 1
    assert view.statuses


# ----------------------------------------------------------------- actions


def test_every_action_is_delegated_to_the_gateway():
    view = FakeView()
    gateway = FakePluginManagerGateway()
    controller = ActionController(gateway, FakeReporter())
    info = makeInfo(1, "SomePlugin")
    for action in ("install", "upgrade", "reinstall", "uninstall"):
        controller.runAction(view, action, info)
    assert gateway.calls == [
        ("install", "SomePlugin"),
        ("upgrade", "SomePlugin"),
        ("reinstall", "SomePlugin"),
        ("uninstall", "SomePlugin"),
    ]


def test_action_without_selection_is_ignored():
    view = FakeView()
    gateway = FakePluginManagerGateway()
    controller = ActionController(gateway, FakeReporter())
    controller.runAction(view, "install", None)
    assert gateway.calls == []
    assert view.statuses


def test_unknown_action_is_reported():
    view = FakeView()
    controller = ActionController(FakePluginManagerGateway(), FakeReporter())
    controller.runAction(view, "transmogrify", makeInfo(1, "X"))
    assert any("unknown action" in message.lower() for message in view.statuses)


def test_gateway_failure_is_surfaced_not_raised():
    class FailingGateway(FakePluginManagerGateway):
        def install(self, pluginName: str) -> None:
            raise RuntimeError("installer exploded")

    view = FakeView()
    reporter = FakeReporter()
    controller = ActionController(FailingGateway(), reporter)
    controller.runAction(view, "install", makeInfo(1, "X"))
    assert reporter.errors
    assert any("failed" in message.lower() for message in view.statuses)


def test_action_states_come_from_the_gateway():
    view = FakeView()
    gateway = FakePluginManagerGateway()
    gateway.nextStates = ActionStates(canUpgrade=True, installedVersion="1.0.0")
    controller = ActionController(gateway, FakeReporter())
    controller.refreshStates(view, makeInfo(1, "X"), "2.0.0")
    assert view.actionStates[-1].canUpgrade is True
    assert view.actionStates[-1].canInstall is False


def test_action_states_without_selection_disable_everything():
    view = FakeView()
    controller = ActionController(FakePluginManagerGateway(), FakeReporter())
    controller.refreshStates(view, None, "1.0.0")
    states = view.actionStates[-1]
    assert not states.canInstall and not states.canUpgrade
    assert not states.canReinstall and not states.canUninstall
