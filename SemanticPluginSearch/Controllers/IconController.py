"""Icon orchestration: background fetch of the row icons.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from collections.abc import Callable

from ..Domain.Entities import SearchResult
from ..Domain.Ports import JobRunner


class IconController:
    """Fetches each result icon off the GUI thread, with a local cache."""

    def __init__(self, iconGateway, runner: JobRunner) -> None:  # noqa: ANN001
        self.iconGateway = iconGateway
        self.runner = runner

    def fetchFor(self, results: list[SearchResult], onIcon: Callable[[int, bytes], None]) -> None:
        """Fetch icons for every result that has an icon URL.

        onIcon is called per icon on the GUI thread (the runner marshals);
        icons without a URL and failed fetches are silently skipped: a row
        simply keeps its empty icon slot.
        """
        for result in results:
            url = result.info.iconUrl
            if not url:
                continue
            pluginId = result.info.pluginId
            self.runner.submit(
                lambda url=url: self.iconGateway.fetchIcon(url),
                lambda payload, pluginId=pluginId: onIcon(pluginId, payload),
                lambda error, pluginId=pluginId: None,
            )
