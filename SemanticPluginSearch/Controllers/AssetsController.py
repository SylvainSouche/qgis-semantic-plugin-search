"""Asset orchestration: keep the cached model and database current.

Opening the window loads the LOCAL cache immediately (offline safe, no
round trip) and then checks the published index in the background; the
fresh store is only handed back when something actually changed, so the
user's selection never jumps after a no-op refresh. Every failure leaves
the previous cache untouched and usable.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..Data.AssetGateways import ChecksumMismatch, TransportError
from ..Data.SqliteVectorStore import (
    DatabaseMissingError,
    SqliteVectorStore,
    readDatabaseMeta,
)
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
        """Load the cache at once, then check the index in the background.

        Two jobs, one event each: the cached store reaches the window
        without any network round trip (offline first), and the refresh
        only re-delivers when a download changed something.
        """
        self.runner.submit(
            self._loadCachedTask, self.onStoreReady, lambda error: None
        )
        self.runner.submit(self._refreshTask, self._onRefreshed, self._onRefreshFailed)

    def _loadCachedTask(self) -> PluginVectorStore:
        return SqliteVectorStore.open(
            self.paths.databasePath(self.versionProvider.universe())
        )

    def _refreshTask(self) -> PluginVectorStore | None:
        index = self.gateway.fetchIndex()
        universe = self.versionProvider.universe()
        modelChanged = self.ensureModel(index)
        databaseChanged = self.ensureDatabase(index, universe)
        if not (modelChanged or databaseChanged):
            return None
        return SqliteVectorStore.open(self.paths.databasePath(universe))

    def ensureModel(self, index: RemoteIndex) -> bool:
        """Download the embedding model when missing or stale; True if so."""
        modelPath = self.paths.modelPath()
        stampPath = self.paths.cacheDir() / MODEL_STAMP_NAME
        if modelPath.is_file() and _stampMatches(stampPath, index.model.sha256):
            return False
        self.reporter.info("Downloading the embedding model…")
        self.gateway.downloadVerified(index.model, modelPath)
        stampPath.parent.mkdir(parents=True, exist_ok=True)
        stampPath.write_text(
            json.dumps({"sha256": index.model.sha256}), encoding="utf-8"
        )
        return True

    def ensureDatabase(self, index: RemoteIndex, universe: str) -> bool:
        """Download the universe database when missing or stale; True if so."""
        release = index.universes.get(universe)
        if release is None:
            raise RuntimeError(f"No published database for QGIS {universe}.")
        databasePath = self.paths.databasePath(universe)
        if databasePath.is_file():
            localStamp = _localBuildStamp(databasePath)
            if localStamp and not _stampIsNewer(localStamp, release.buildStamp):
                return False
            self.reporter.info(
                f"Updating the embeddings database (build {release.buildStamp})…"
            )
        else:
            self.reporter.info("Downloading the embeddings database (first run only)…")
        self.gateway.downloadVerified(release.database, databasePath)
        return True

    def _onRefreshed(self, store: PluginVectorStore | None) -> None:
        if store is not None:
            self.onStoreReady(store)

    def _onRefreshFailed(self, error: Exception) -> None:
        if isinstance(error, ChecksumMismatch):
            # A published artifact changed under us: surface it loudly and
            # keep the last good cache.
            self.reporter.error(
                f"Downloaded embeddings asset failed its integrity check: {error}"
            )
        elif isinstance(error, DatabaseMissingError):
            # No cache yet: the refresh job downloads it and reports its own
            # outcome; nothing to add here.
            return
        elif isinstance(error, TransportError):
            self.reporter.warn(
                f"Cannot refresh the embeddings assets ({error}); using cached data."
            )
        else:
            self.reporter.error(f"Embeddings update failed: {error}")


STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def _stampIsNewer(local: str, remote: str) -> bool:
    """True when remote is strictly newer than local.

    Stamps are UTC timestamps; compare them as datetimes and fall back to
    the lexicographic order if either does not parse.
    """
    try:
        localTime = datetime.strptime(local, STAMP_FORMAT)
        remoteTime = datetime.strptime(remote, STAMP_FORMAT)
        return remoteTime > localTime
    except ValueError:
        return remote > local


def _stampMatches(stampPath: Path, sha256: str) -> bool:
    try:
        stamp = json.loads(stampPath.read_text(encoding="utf-8"))
        return stamp.get("sha256") == sha256
    except (OSError, ValueError):
        return False


def _localBuildStamp(databasePath: Path) -> str:
    """Read only the build stamp, without loading the whole store."""
    try:
        return readDatabaseMeta(databasePath, "build_stamp")
    except (DatabaseMissingError, ValueError, OSError):
        return ""

# @impl 0f87-6ae3-6985-6264
# @impl 0f87-6ae3-6985-a030
