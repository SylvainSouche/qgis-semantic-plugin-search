"""View protocols the controllers drive.

The Presentation layer implements these methods structurally: it never
imports the controllers, and the controllers never import Qt. The
indirection keeps both sides independently testable.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from typing import Protocol

from ..Domain.Entities import ActionStates, PluginInfo, SearchResult


class SearchWindowView(Protocol):
    """The full search window surface the controllers may drive."""

    def showResults(self, results: list[SearchResult]) -> None:
        """Replace the list contents; select the first row by default."""
        ...

    def showStatus(self, message: str) -> None:
        """Show a transient status line inside the window."""
        ...

    def showMetadata(self, info: PluginInfo) -> None:
        """Fill the metadata tab."""
        ...

    def showReadme(self, pluginId: int, text: str) -> None:
        """Fill the readme tab for the given plugin."""
        ...

    def showReadmePlaceholder(self, pluginId: int, message: str) -> None:
        """Show a placeholder in the readme tab (loading, failure, absence)."""
        ...

    def setActionStates(self, states: ActionStates) -> None:
        """Enable or disable the manager action buttons."""
        ...

    def clearDetails(self) -> None:
        """Reset the right panel, e.g. when no result exists."""
        ...
