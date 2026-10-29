"""Asset orchestration: keep the cached model and database current.

On window opening this controller checks the published index in the
background, downloads anything stale or missing for the running QGIS
universe, and hands the fresh store back in one atomic step. Every failure
leaves the previous cache untouched and usable.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..Data.AssetGateways import ChecksumMismatch, TransportError
from ..Data.SqliteVectorStore import DatabaseMissingError, SqliteVectorStore
from ..Domain.Entities import RemoteIndex
from ..Domain.Ports import (
    AssetGateway,
    JobRunner,
    PathsProvider,
    PluginVectorStore,
    Reporter,
    VersionProvider,
)

MODEL_STAMP_NAME = "Model.stamp.json"


class AssetsController:
    """Bootstrap and update of the cached embedding assets."""

    def __init__(
        self,
        gateway: AssetGateway,
        paths: PathsProvider,
        versionProvider: VersionProvider,
        runner: JobRunner,
        reporter: Reporter,
        onStoreReady: Callable[[PluginVectorStore], None],
    ) -> None:
        self.gateway = gateway
        self.paths = paths
        self.versionProvider = versionProvider
        self.runner = runner
        self.reporter = reporter
        self.onStoreReady = onStoreReady

    def refresh(self) -> None:
        """Check the index and update the cache for this QGIS universe."""
        self.runner.submit(self._refreshTask, self._onRefreshed, self._onRefreshFailed)

    def _refreshTask(self) -> PluginVectorStore:
        index = self.gateway.fetchIndex()
        universe = self.versionProvider.universe()
        self.ensureModel(index)
        self.ensureDatabase(index, universe)
        return SqliteVectorStore.open(self.paths.databasePath(universe))

    def ensureModel(self, index: RemoteIndex) -> None:
        """Download the embedding model when missing or different from published."""
        modelPath = self.paths.modelPath()
        stampPath = self.paths.cacheDir() / MODEL_STAMP_NAME
        if modelPath.is_file() and _stampMatches(stampPath, index.model.sha256):
            return
        self.reporter.info("Downloading the embedding model…")
        self.gateway.downloadVerified(index.model, modelPath)
        stampPath.parent.mkdir(parents=True, exist_ok=True)
        stampPath.write_text(
            json.dumps({"sha256": index.model.sha256}), encoding="utf-8"
        )

    def ensureDatabase(self, index: RemoteIndex, universe: str) -> None:
        """Download the universe database when missing or older than published."""
        release = index.universes.get(universe)
        if release is None:
            raise RuntimeError(f"No published database for QGIS {universe}.")
        databasePath = self.paths.databasePath(universe)
        if databasePath.is_file():
            localStamp = _localBuildStamp(databasePath)
            if localStamp and localStamp >= release.buildStamp:
                return
            self.reporter.info(
                f"Updating the embeddings database (build {release.buildStamp})…"
            )
        else:
            self.reporter.info("Downloading the embeddings database (first run only)…")
        self.gateway.downloadVerified(release.database, databasePath)

    def _onRefreshed(self, store: PluginVectorStore) -> None:
        self.onStoreReady(store)

    def _onRefreshFailed(self, error: Exception) -> None:
        if isinstance(error, ChecksumMismatch):
            # A published artifact changed under us: surface it loudly and
            # keep the last good cache.
            self.reporter.error(
                f"Downloaded embeddings asset failed its integrity check: {error}"
            )
        elif isinstance(error, (TransportError, DatabaseMissingError)):
            self.reporter.warn(
                f"Cannot refresh the embeddings assets ({error}); using cached data."
            )
        else:
            self.reporter.error(f"Embeddings update failed: {error}")


def _stampMatches(stampPath: Path, sha256: str) -> bool:
    try:
        stamp = json.loads(stampPath.read_text(encoding="utf-8"))
        return stamp.get("sha256") == sha256
    except (OSError, ValueError):
        return False


def _localBuildStamp(databasePath: Path) -> str:
    try:
        return SqliteVectorStore.open(databasePath).buildStamp()
    except (DatabaseMissingError, ValueError, OSError):
        return ""

# @impl 0f87-6ae3-6985-6264
# @impl 0f87-6ae3-6985-a030
