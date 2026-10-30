"""Ports: the abstract boundaries the controllers are written against.

Every QGIS or Qt specific service is isolated behind one of these ports and
implemented by an adapter in the QgisBridge or Presentation layer, which keeps
the Domain, Data and Controllers layers importable without QGIS.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import numpy as np

from .Entities import InstalledPlugin, PluginInfo, RemoteFile, RemoteIndex

T = TypeVar("T")


class EmbeddingEngine(ABC):
    """Computes an embedding vector for a natural language query."""

    @abstractmethod
    def embedQuery(self, text: str) -> np.ndarray:
        """Return a normalized vector, or a zero vector for empty input."""
        raise NotImplementedError


class StaticModelData(ABC):
    """Access to the token vocabulary and vectors of the distributed model."""

    @abstractmethod
    def tokenId(self, token: str) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def vectorFor(self, tokenId: int) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def modelId(self) -> str:
        raise NotImplementedError


class PluginVectorStore(ABC):
    """Read side of the local embeddings database."""

    @abstractmethod
    def buildStamp(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def universe(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def modelId(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def pluginIds(self) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def embeddings(self) -> np.ndarray:
        """Matrix aligned with pluginIds, rows L2 normalized."""

    @abstractmethod
    def pluginInfo(self, pluginId: int) -> PluginInfo | None:
        raise NotImplementedError


class AssetGateway(ABC):
    """Remote access to the project published assets (index and binaries)."""

    @abstractmethod
    def fetchIndex(self) -> RemoteIndex:
        raise NotImplementedError

    @abstractmethod
    def downloadVerified(self, remoteFile: RemoteFile, destination: Path) -> None:
        """Download to destination atomically, verifying the checksum first.

        The file must land through a temporary path so a failed download never
        damages an existing cached copy.
        """
        raise NotImplementedError


class ReadmeGateway(ABC):
    """Fetches the readme text of a plugin, from cache or network."""

    @abstractmethod
    def fetchReadme(self, info: PluginInfo) -> str:
        """Return the readme text or raise ReadmeUnavailable."""
        raise NotImplementedError


class PluginManagerGateway(ABC):
    """Delegation to the standard QGIS plugin manager machinery.

    Implementations must defer to pyplugin_installer (or open the plugin
    manager dialog); they must never install or remove anything themselves.
    """

    @abstractmethod
    def install(self, plugin: PluginInfo) -> None:
        raise NotImplementedError

    @abstractmethod
    def upgrade(self, plugin: PluginInfo) -> None:
        raise NotImplementedError

    @abstractmethod
    def reinstall(self, plugin: PluginInfo) -> None:
        raise NotImplementedError

    @abstractmethod
    def uninstall(self, plugin: PluginInfo) -> None:
        raise NotImplementedError

    @abstractmethod
    def installedPlugins(self) -> dict[str, InstalledPlugin]:
        """A fresh snapshot of the installed plugins, keyed by installer key.

        The Domain (Domain.Installed) turns it into action states and badges.
        """
        raise NotImplementedError


class Reporter(ABC):
    """User facing status reporting."""

    @abstractmethod
    def info(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def warn(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(self, message: str) -> None:
        raise NotImplementedError


class JobRunner(ABC):
    """Runs work off the GUI thread and marshals the outcome back."""

    @abstractmethod
    def submit(
        self,
        task: Callable[[], T],
        on_success: Callable[[T], None],
        on_failure: Callable[[Exception], None],
    ) -> None:
        raise NotImplementedError


class VersionProvider(ABC):
    """The QGIS version the plugin is running in."""

    @abstractmethod
    def universe(self) -> str:
        """Return the QGIS major version universe, "3" or "4"."""
        raise NotImplementedError

    @abstractmethod
    def qgisVersion(self) -> str:
        raise NotImplementedError


class PathsProvider(ABC):
    """Local cache locations, independent of plugin upgrades."""

    @abstractmethod
    def cacheDir(self) -> Path:
        """Return (and create if needed) the per profile cache directory."""
        raise NotImplementedError

    @abstractmethod
    def modelPath(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def databasePath(self, universe: str) -> Path:
        raise NotImplementedError
