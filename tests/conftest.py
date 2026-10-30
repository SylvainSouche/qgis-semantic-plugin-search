"""Shared fixtures: a tiny deterministic static model, a fixture catalogue,
and the fakes every layer needs. The whole suite runs without QGIS installed
and without importing qgis or Qt.

# @impl 0f87-6ae3-6986-4c12
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from SemanticPluginSearch.Data.StaticModelLoader import (  # noqa: E402
    FORMAT_ID,
    KEY_META,
    KEY_TOKENS,
    KEY_VECTORS,
    TOKENIZER_ID,
)
from SemanticPluginSearch.Domain.WordPieceTokenizer import WordPieceTokenizer  # noqa: E402

DIM = 8

# Four semantic clusters on orthogonal axes, plus control tokens.
CLUSTERS = {
    "geo": 0,
    "web": 1,
    "office": 2,
    "data": 3,
}
VOCABULARY_WORDS = {
    "geo": [
        "parcel", "parcels", "cadastre", "cadastral", "digitize", "boundary",
        "boundaries", "orthophoto", "drone", "land", "cover", "contour",
        "elevation", "raster", "geometry", "coordinate",
    ],
    "web": [
        "wfs", "wms", "api", "layer", "layers", "service", "url", "request",
        "online", "http",
    ],
    "office": [
        "invoice", "invoices", "accounting", "budget", "report", "reports",
        "export", "pdf", "excel", "revenue",
    ],
    "data": [
        "classify", "classification", "machine", "learning", "model",
        "training", "prediction", "statistics", "analysis", "imagery",
    ],
}
SPECIAL_TOKENS = [
    "[UNK]", "[CLS]", "[SEP]", "[MASK]", "[PAD]", "##ing", "##s",
    ",", ".", ";", ":", "(", ")",
]

FIXTURE_PLUGINS = {
    1: {
        "name": "ParcelDigitizer",
        "version": "1.2.0",
        "icon": "/media/packages/parcel.png",
        "description": "Digitize parcel boundaries from cadastre maps",
        "about": "Parcel and cadastre digitizing with boundary tracing tools",
        "tags": "parcel,cadastre,digitizing",
        "readme": (
            "# Parcel Digitizer\n\nDigitize parcel boundaries and cadastral "
            "lots. Boundary tracing for cadastre work.\n"
        ),
    },
    2: {
        "name": "OrthoClassifier",
        "version": "0.9.1",
        "description": "Classify drone orthophotos into land cover classes with machine learning",
        "about": "Machine learning classification of orthophoto imagery into land cover",
        "tags": "classification,machine learning,orthophoto",
        "readme": (
            "# OrthoClassifier\n\nClassify drone orthophoto imagery into land "
            "cover classes with machine learning models.\n"
        ),
    },
    3: {
        "name": "InvoiceReporter",
        "version": "2.0.3",
        "experimental": True,
        "description": "Generate invoices and accounting reports as pdf",
        "about": "Accounting and invoice report export",
        "tags": "invoice,accounting,pdf",
        "readme": "# InvoiceReporter\n\nInvoices, accounting and budget reports.\n",
    },
    4: {
        "name": "WebLayerLoader",
        "version": "1.0.0",
        "description": "Load WFS and WMS layers from online services",
        "about": "Add wfs and wms service layers by url",
        "tags": "wfs,wms,layer",
        "readme": "# WebLayerLoader\n\nLoad WFS and WMS layers from a service url.\n",
    },
    5: {
        "name": "ShapeExporter",
        "version": "0.5.0",
        "description": "Export layers to shapefiles, superseded by modern formats",
        "about": "Legacy shapefile export kept for old projects",
        "tags": "export,shapefile",
        "readme": "# ShapeExporter\n\nLegacy export of layers to shapefiles.\n",
        "deprecated": True,
    },
}


def buildFixtureVectors() -> tuple[dict[str, int], np.ndarray]:
    vocabulary: dict[str, int] = {}
    words: list[str] = []
    for name in SPECIAL_TOKENS:
        vocabulary[name] = len(words)
        words.append(name)
    for clusterName in CLUSTERS:
        for word in VOCABULARY_WORDS[clusterName]:
            vocabulary[word] = len(words)
            words.append(word)
    vectors = np.zeros((len(words), DIM), dtype=np.float32)
    for clusterName, axis in CLUSTERS.items():
        for position, word in enumerate(VOCABULARY_WORDS[clusterName]):
            index = vocabulary[word]
            vectors[index, axis] = 1.0
            vectors[index, 4 + (position % 4)] = 0.01 * position
    for index in range(len(SPECIAL_TOKENS)):
        vectors[index, 7] = 0.001  # control tokens barely influence the mean
    return vocabulary, vectors


def writeFixtureModel(path: Path, vocabulary=None, vectors=None) -> None:
    if vocabulary is None:
        vocabulary, vectors = buildFixtureVectors()
    order = sorted(vocabulary.items(), key=lambda item: item[1])
    tokens = np.array([token for token, _ in order], dtype=np.str_)
    meta = json.dumps(
        {
            "format": FORMAT_ID,
            "tokenizer": TOKENIZER_ID,
            "model_id": "fixture-static-model",
            "dim": int(vectors.shape[1]),
            "license": "test fixture, never published",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        **{KEY_TOKENS: tokens, KEY_VECTORS: vectors, KEY_META: np.array(meta)},
    )


def fixtureTokenizer() -> WordPieceTokenizer:
    vocabulary, _ = buildFixtureVectors()
    return WordPieceTokenizer(vocabulary)


def fixtureCatalogueBytes() -> bytes:
    entries = []
    for pluginId, spec in FIXTURE_PLUGINS.items():
        entries.append(
            f"""<pyqgis_plugin name="{spec['name']}" version="{spec['version']}" plugin_id="{pluginId}">
        <description><![CDATA[{spec['description']}]]></description>
        <about><![CDATA[{spec['about']}]]></about>
        <qgis_minimum_version>3.34.0</qgis_minimum_version>
        <qgis_maximum_version>4.99.0</qgis_maximum_version>
        <author_name><![CDATA[Fixture Author]]></author_name>
        <download_url>https://plugins.qgis.org/plugins/{spec['name']}/download/</download_url>
        <file_name>{spec['name']}.{spec['version']}.zip</file_name>
        <icon>{spec.get('icon', '')}</icon>
        <experimental>{'True' if spec.get('experimental') else 'False'}</experimental>
        <deprecated>{'True' if spec.get('deprecated') else 'False'}</deprecated>
        <repository><![CDATA[https://github.com/fixture/{spec['name']}]]></repository>
        <tags><![CDATA[{spec['tags']}]]></tags>
        <downloads>1000</downloads>
        <average_vote>4.5</average_vote>
        <rating_votes>10</rating_votes>
        <server>False</server>
    </pyqgis_plugin>"""
        )
    return ("<plugins>" + "".join(entries) + "</plugins>").encode("utf-8")


@pytest.fixture(scope="session")
def modelPath(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("model") / "EmbeddingModel.npz"
    writeFixtureModel(path)
    return path


@pytest.fixture()
def catalogueAndReadmes(tmp_path: Path) -> tuple[Path, Path]:
    catalogue = tmp_path / "plugins-4.2.xml"
    catalogue.write_bytes(fixtureCatalogueBytes())
    readmeDir = tmp_path / "plugins-4.2"
    readmeDir.mkdir()
    for spec in FIXTURE_PLUGINS.values():
        safeName = spec["name"]
        (readmeDir / f"{safeName}.md").write_text(spec["readme"], encoding="utf-8")
    return catalogue, readmeDir


# ---------------------------------------------------------------- fakes


class FakeView:
    """Records every call the controllers make on the window protocol."""

    def __init__(self) -> None:
        self.results: list = []
        self.statuses: list[str] = []
        self.summaries: list[str] = []
        self.metadata: list = []
        self.readmes: list[tuple[int, str]] = []
        self.placeholders: list[tuple[int, str]] = []
        self.actionStates: list = []
        self.badges: list[dict] = []
        self.cleared = 0
        self.detailsDriver = None  # set to (details, view) to mimic wiring

    def showResults(self, results) -> None:  # noqa: ANN001
        self.results = list(results)
        # The real dialog defaults the details to the first row.
        if self.results and self.detailsDriver is not None:
            details, view = self.detailsDriver
            details.showDetails(view, self.results[0].info)

    def showStatus(self, message: str) -> None:
        self.statuses.append(message)

    def showSearchSummary(self, message: str) -> None:
        self.summaries.append(message)

    def showMetadata(self, info) -> None:  # noqa: ANN001
        self.metadata.append(info)

    def showReadme(self, pluginId: int, text: str) -> None:
        self.readmes.append((pluginId, text))

    def showReadmePlaceholder(self, pluginId: int, message: str) -> None:
        self.placeholders.append((pluginId, message))

    def setActionStates(self, states) -> None:  # noqa: ANN001
        self.actionStates.append(states)

    def showInstalledBadges(self, badges) -> None:  # noqa: ANN001
        self.badges.append(dict(badges))

    def clearDetails(self) -> None:
        self.cleared += 1


class FakeReporter:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


class InlineRunner:
    """Runs jobs synchronously, like the Qt runner would after marshaling."""

    def submit(self, task, on_success, on_failure) -> None:  # noqa: ANN001
        try:
            on_success(task())
        except Exception as error:  # noqa: BLE001
            on_failure(error)


class ManualRunner:
    """Holds tasks so tests control completion order (staleness tests)."""

    def __init__(self) -> None:
        self.pending: list[tuple] = []

    def submit(self, task, on_success, on_failure) -> None:  # noqa: ANN001
        self.pending.append((task, on_success, on_failure))

    def completeNext(self) -> None:
        task, on_success, on_failure = self.pending.pop(0)
        try:
            on_success(task())
        except Exception as error:  # noqa: BLE001
            on_failure(error)


class FakePluginManagerGateway:
    """Records delegation calls; performs nothing itself."""

    def __init__(self, installed=None) -> None:  # noqa: ANN001
        self.calls: list[tuple[str, str]] = []
        self.installed = dict(installed or {})

    def install(self, plugin) -> None:  # noqa: ANN001
        self.calls.append(("install", plugin.name))

    def upgrade(self, plugin) -> None:  # noqa: ANN001
        self.calls.append(("upgrade", plugin.name))

    def reinstall(self, plugin) -> None:  # noqa: ANN001
        self.calls.append(("reinstall", plugin.name))

    def uninstall(self, plugin) -> None:  # noqa: ANN001
        self.calls.append(("uninstall", plugin.name))

    def installedPlugins(self):  # noqa: ANN201
        return dict(self.installed)


class FakeIconGateway:
    """Records icon fetches; serves deterministic bytes; can fail per url."""

    def __init__(self) -> None:
        self.fetched: list[str] = []

    def fetchIcon(self, url: str) -> bytes:  # noqa: D102
        self.fetched.append(url)
        return b"png:" + url.encode()


class FakePaths:
    def __init__(self, root: Path) -> None:
        self.root = root / "cache"

    def cacheDir(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def modelPath(self) -> Path:
        return self.cacheDir() / "EmbeddingModel.npz"

    def databasePath(self, universe: str) -> Path:
        return self.cacheDir() / f"Embeddings-{universe}.sqlite"


class FakeVersionProvider:
    def __init__(self, universe: str = "4") -> None:
        self._universe = universe

    def universe(self) -> str:
        return self._universe

    def qgisVersion(self) -> str:
        return "4.2.0"


class FakeReadmeGateway:
    def __init__(self, texts: dict[int, str] | None = None) -> None:
        self.texts = texts or {}
        self.failures: set[int] = set()
        self.calls: list[int] = []

    def fetchReadme(self, info) -> str:  # noqa: ANN001
        self.calls.append(info.pluginId)
        if info.pluginId in self.failures:
            raise RuntimeError("network down")
        return self.texts.get(info.pluginId, f"readme of {info.name}")
