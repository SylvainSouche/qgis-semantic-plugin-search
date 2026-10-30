"""Icon orchestration: one batched background fetch per result batch.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from collections.abc import Callable

from ..Domain.Entities import SearchResult
from ..Domain.Ports import JobRunner


class IconController:
    """Fetches result icons in ONE background job per result batch.

    Event discipline (every dispatch is treated as multithreaded and
    re-entrant safe): one search produces at most one fetch job and one
    batched GUI callback; each URL is fetched at most once per session;
    callbacks from superseded batches are dropped here, before any view
    update; failures are skipped, never re-raised on the GUI thread.
    """

    def __init__(self, iconGateway, runner: JobRunner) -> None:  # noqa: ANN001
        self.iconGateway = iconGateway
        self.runner = runner
        self._generation = 0
        self._served: set[str] = set()

    def fetchFor(
        self, results: list[SearchResult], onIcons: Callable[[list[tuple[int, bytes]]], None]
    ) -> None:
        """Fetch the missing icons of the batch and deliver them at once.

        onIcons receives a list of (pluginId, iconBytes) on the GUI thread in
        a single call. Icons without a URL, failures and stale batches are
        silently skipped: a row simply keeps its empty icon slot.
        """
        wanted: list[tuple[int, str]] = [
            (result.info.pluginId, result.info.iconUrl)
            for result in results
            if result.info.iconUrl and result.info.iconUrl not in self._served
        ]
        if not wanted:
            return
        self._generation += 1
        generation = self._generation
        urls = [url for _pluginId, url in wanted]

        def task() -> list[tuple[int, bytes]]:
            batch: list[tuple[int, bytes]] = []
            for pluginId, url in wanted:
                try:
                    batch.append((pluginId, self.iconGateway.fetchIcon(url)))
                except Exception:  # noqa: BLE001 - one icon failing is not fatal
                    continue
            return batch

        def deliver(batch: list[tuple[int, bytes]]) -> None:
            self._served.update(urls)
            if generation == self._generation and batch:
                onIcons(batch)

        self.runner.submit(task, deliver, lambda error: None)
