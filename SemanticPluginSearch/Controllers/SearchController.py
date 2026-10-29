"""Search orchestration: user input to ranked results.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import PluginInfo, SearchResult
from ..Domain.Ports import EmbeddingEngine, PluginVectorStore, Reporter
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
