"""Search orchestration: user input to ranked results.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import SearchResult
from ..Domain.Ports import EmbeddingEngine, PluginVectorStore, Reporter
from ..Domain.SearchEngine import SearchService, visibilityPredicate
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
        self.includeExperimental = False
        self.includeDeprecated = False
        self._lastQuery: str | None = None

    def setStore(self, store: PluginVectorStore | None) -> None:
        self.store = store
        self._lastQuery = None  # a fresh store invalidates the last query

    def setFilters(self, includeExperimental: bool, includeDeprecated: bool) -> None:
        """Apply the visibility toggles; the next search uses them."""
        self.includeExperimental = includeExperimental
        self.includeDeprecated = includeDeprecated

    def search(self, view: SearchWindowView, text: str) -> None:
        """Run the query and push the ranked list to the view.

        Cancellation semantics: the search is synchronous on the caller
        thread, so a newer query always supersedes the older one; query
        multiplication is prevented at the view (debounce plus separator
        trigger), and background deliverables (icons, readmes) carry
        staleness tokens of their own and are dropped when superseded.
        """
        if self.store is None:
            message = "No embeddings database available yet."
            self.reporter.warn(message)
            view.showStatus(message)
            view.showResults([])
            view.clearDetails()
            return
        results = self.searchService.search(
            self.store,
            text,
            predicate=visibilityPredicate(
                self.includeExperimental, self.includeDeprecated
            ),
        )
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
        return self.searchService.search(
            self.store,
            text,
            predicate=visibilityPredicate(
                self.includeExperimental, self.includeDeprecated
            ),
        )

# @impl 0f87-6ae3-a1e6-cf4c
