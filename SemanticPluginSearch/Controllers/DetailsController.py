"""Details orchestration: selection to metadata display and readme loading.

The metadata tab is filled synchronously from the store snapshot; the readme
tab is filled by a background job so a slow network never blocks the list.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import PluginInfo
from ..Domain.Ports import JobRunner, ReadmeGateway
from .ViewPorts import SearchWindowView


class DetailsController:
    """Drives the right panel: metadata now, readme in the background."""

    def __init__(self, readmeGateway: ReadmeGateway, runner: JobRunner) -> None:
        self.readmeGateway = readmeGateway
        self.runner = runner
        self._displayedPluginId: int | None = None
        self._inflightReadmes: set[int] = set()

    def showDetails(self, view: SearchWindowView, info: PluginInfo) -> None:
        """Display metadata for the plugin and start its readme fetch."""
        self._displayedPluginId = info.pluginId
        view.showMetadata(info)
        if info.readmeUrl or info.repository:
            if info.pluginId not in self._inflightReadmes:
                # One background fetch per plugin at a time: reselecting the
                # same row never multiplies identical jobs.
                view.showReadmePlaceholder(info.pluginId, "Loading readme…")
                self._inflightReadmes.add(info.pluginId)
                self.runner.submit(
                    lambda: self.readmeGateway.fetchReadme(info),
                    lambda text, info=info: self._onReadme(view, info, text),
                    lambda error, info=info: self._onReadmeFailure(view, info, error),
                )
        else:
            view.showReadmePlaceholder(
                info.pluginId, "No readme is available for this plugin."
            )

    def _onReadme(self, view: SearchWindowView, info: PluginInfo, text: str) -> None:
        self._inflightReadmes.discard(info.pluginId)
        # The job completed after the selection moved on: drop the result.
        if self._displayedPluginId != info.pluginId:
            return
        view.showReadme(info.pluginId, text)

    def _onReadmeFailure(
        self, view: SearchWindowView, info: PluginInfo, error: Exception
    ) -> None:
        self._inflightReadmes.discard(info.pluginId)
        if self._displayedPluginId != info.pluginId:
            return
        view.showReadmePlaceholder(
            info.pluginId,
            f"Readme could not be loaded: {error}\n"
            "You can open the plugin repository instead:\n"
            f"{info.repository or 'unknown'}",
        )

    def displayedPluginId(self) -> int | None:
        return self._displayedPluginId

# @impl 0f87-6ae3-6985-9f7c
