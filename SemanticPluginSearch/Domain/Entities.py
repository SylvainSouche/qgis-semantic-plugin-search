"""Value objects shared by every layer.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PluginInfo:
    """Metadata snapshot of one plugin, as stored in the embeddings database."""

    pluginId: int
    name: str
    version: str = ""
    author: str = ""
    description: str = ""
    about: str = ""
    tags: tuple[str, ...] = ()
    repository: str = ""
    homepage: str = ""
    tracker: str = ""
    downloadUrl: str = ""
    fileName: str = ""
    iconUrl: str = ""
    downloads: int = 0
    averageVote: float = 0.0
    votes: int = 0
    experimental: bool = False
    deprecated: bool = False
    server: bool = False
    qgisMinimum: str = ""
    qgisMaximum: str = ""
    readmeUrl: str = ""
    updateDate: str = ""

    def tagText(self) -> str:
        return ", ".join(self.tags)


@dataclass(frozen=True)
class SearchResult:
    """One ranked hit: the plugin, its ranking score and its cosine similarity.

    score is the hybrid ranking score, the cosine similarity plus the lexical
    boost (Domain.LexicalBoost), capped at 1.0; semantic is the cosine part
    alone. Results built without a boost carry score as their semantic part.
    """

    info: PluginInfo
    score: float
    semantic: float | None = None


@dataclass(frozen=True)
class RemoteFile:
    """A downloadable artifact published by the project GitHub."""

    url: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class UniverseRelease:
    """The embeddings database published for one QGIS version universe."""

    database: RemoteFile
    buildStamp: str
    pluginCount: int


@dataclass(frozen=True)
class RemoteIndex:
    """Content of the published index file describing available assets."""

    generatedAt: str
    model: RemoteFile
    modelId: str
    modelDim: int
    universes: dict[str, UniverseRelease] = field(default_factory=dict)


@dataclass(frozen=True)
class InstalledPlugin:
    """One plugin folder found on disk: its installer key and metadata."""

    key: str
    name: str = ""
    version: str = ""


@dataclass(frozen=True)
class ActionStates:
    """Availability of the manager actions for the currently selected plugin."""

    canInstall: bool = False
    canUpgrade: bool = False
    canReinstall: bool = False
    canUninstall: bool = False
    installedVersion: str = ""
