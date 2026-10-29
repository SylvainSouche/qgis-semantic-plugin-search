"""Search orchestration: user input to ranked results.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import ActionStates, PluginInfo, SearchResult
from ..Domain.Ports import EmbeddingEngine, PluginManagerGateway, PluginVectorStore, Reporter
from ..Domain.SearchEngine import SearchService
from .ViewPorts import SearchWindowView


class SearchController:
    """Answers queries against the current store and reports the ranking."""

    def __init__(
        self,
        engine: EmbeddingEngine,
        searchService: SearchService,
        reporter: Reporter,
    ) -> None:
        self.engine = engine
        self.searchService = searchService
        self.reporter = reporter
        self.store: PluginVectorStore | None = None

    def setStore(self, store: PluginVectorStore | None) -> None:
        self.store = store

    def search(self, view: SearchWindowView, text: str) -> None:
        """Run the query and push the ranked list to the view."""
        if self.store is None:
            message = "No embeddings database available yet."
            self.reporter.warn(message)
            view.showStatus(message)
            view.showResults([])
            view.clearDetails()
            return
        results = self.searchService.search(self.store, text)
        view.showResults(results)
        if results:
            view.showStatus(
                f"{len(results)} plugin(s) match; showing similarity as a percentage."
            )
        else:
            view.showStatus("No plugin matches this query closely enough.")

    def resultsOf(self, text: str) -> list[SearchResult]:
        """Ranking without a view, used by tests and keyboard navigation."""
        if self.store is None:
            return []
        return self.searchService.search(self.store, text)


class ActionController:
    """Forwards manager actions to the plugin manager gateway.

    The controller holds no installation logic whatsoever: every operation
    is delegated to the PluginManagerGateway, whose QGIS adapter calls the
    standard plugin manager machinery.
    """

    def __init__(
        self,
        gateway: PluginManagerGateway,
        reporter: Reporter,
    ) -> None:
        self.gateway = gateway
        self.reporter = reporter

    def runAction(self, view: SearchWindowView, action: str, info: PluginInfo | None) -> None:
        if info is None:
            view.showStatus("Select a plugin first.")
            return
        handlers = {
            "install": (self.gateway.install, "Installing"),
            "upgrade": (self.gateway.upgrade, "Upgrading"),
            "reinstall": (self.gateway.reinstall, "Reinstalling"),
            "uninstall": (self.gateway.uninstall, "Uninstalling"),
        }
        handler = handlers.get(action)
        if handler is None:
            view.showStatus(f"Unknown action: {action}")
            return
        operation, label = handler
        view.showStatus(f"{label} {info.name} through the plugin manager…")
        try:
            operation(info.name)
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            self.reporter.error(f"{label} {info.name} failed: {error}")
            view.showStatus(f"{label} failed: {error}")
            return
        view.showStatus(f"{label} handed to the plugin manager.")

    def refreshStates(self, view: SearchWindowView, info: PluginInfo | None, availableVersion: str) -> None:
        """Ask the manager which actions apply to the current selection."""
        if info is None:
            view.setActionStates(ActionStates())
            return
        try:
            states = self.gateway.actionStates(info.name, availableVersion)
        except Exception as error:  # noqa: BLE001 - conservative fallback
            self.reporter.warn(f"Plugin manager state unavailable: {error}")
            states = ActionStates()
        view.setActionStates(states)

# @impl 0f87-6ae3-6985-0cec
# @impl 0f87-6ae3-6996-c732
