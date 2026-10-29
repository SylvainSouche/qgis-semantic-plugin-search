"""Cache locations inside the QGIS profile directory.

Assets live under <profile>/semantic-search so they survive plugin upgrades
and stay per profile.
"""
from __future__ import annotations

from pathlib import Path

from qgis.core import QgsApplication

from ..Domain.Ports import PathsProvider

CACHE_DIR_NAME = "semantic-search"
MODEL_FILE_NAME = "EmbeddingModel.npz"
DATABASE_FILE_NAME = "Embeddings-{universe}.sqlite"


class ProfilePathsProvider(PathsProvider):
    """Resolves asset paths inside the active QGIS profile."""

    def __init__(self, rootDir: Path | None = None) -> None:
        self._rootDir = rootDir

    def cacheDir(self) -> Path:
        directory = self._rootDir or (
            Path(QgsApplication.qgisSettingsDirPath()) / CACHE_DIR_NAME
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def modelPath(self) -> Path:
        return self.cacheDir() / MODEL_FILE_NAME

    def databasePath(self, universe: str) -> Path:
        return self.cacheDir() / DATABASE_FILE_NAME.format(universe=universe)
