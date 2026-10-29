"""Asset refresh flow against a simulated GitHub release
(t-db-update-flow): bootstrap, no-op when current, update when newer,
offline fallback, and integrity enforcement with atomic replace.
"""
from __future__ import annotations

import json

import pytest

from pipeline.PluginCatalogue import parseCatalogue
from SemanticPluginSearch.Controllers.AssetsController import AssetsController
from SemanticPluginSearch.Data.AssetGateways import HttpAssetGateway, TransportError
from SemanticPluginSearch.Data.SqliteVectorStore import SqliteVectorStore
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from pipeline.BuildEmbeddings import EmbeddingDatabaseWriter
from pipeline.WriteReleaseIndex import buildIndex
from tests.conftest import FIXTURE_PLUGINS
from tests.conftest import (
    FakePaths,
    FakeReporter,
    FakeVersionProvider,
    InlineRunner,
    fixtureTokenizer,
)


class SimulatedGithub:
    """Serves index.json and binaries from an in memory dict of payloads."""

    def __init__(self, indexUrl: str, index: dict, payloads: dict[str, bytes]) -> None:
        self.indexUrl = indexUrl
        self.index = index
        self.payloads = payloads
        self.downloads: list[str] = []
        self.failOnUrl: str | None = None

    def transport(self, url: str) -> bytes:
        if url == self.failOnUrl:
            raise TransportError("network unreachable")
        if url == self.indexUrl:
            return json.dumps(self.index).encode("utf-8")
        self.downloads.append(url)
        return self.payloads[url]


@pytest.fixture()
def published(tmp_path, modelPath, catalogueAndReadmes):
    """Two builds: the current local one and a newer remote one."""
    catalogue, readmeDir = catalogueAndReadmes
    model = NpzStaticModel.load(modelPath)
    writer = EmbeddingDatabaseWriter(model, fixtureTokenizer())
    records = parseCatalogue(catalogue.read_bytes())
    oldDb = tmp_path / "old" / "Embeddings-4.sqlite"
    newDb = tmp_path / "new" / "Embeddings-4.sqlite"
    writer.build(records, readmeDir, "4", oldDb, "20261001T000000Z", "fixture")
    writer.build(records, readmeDir, "4", newDb, "20261029T120000Z", "fixture")
    payloads = {
        f"model://{modelPath.name}": modelPath.read_bytes(),
        f"db://old.sqlite": oldDb.read_bytes(),
        f"db://new.sqlite": newDb.read_bytes(),
    }
    oldIndex = buildIndex(
        modelPath=modelPath,
        databases={"4": oldDb},
        baseUrl="https://example.test/releases/latest/download",
        generatedAt="20261001T000000Z",
    )
    newIndex = buildIndex(
        modelPath=modelPath,
        databases={"4": newDb},
        baseUrl="https://example.test/releases/latest/download",
        generatedAt="20261029T120000Z",
    )
    # The index URLs point at the simulated transport scheme.
    oldIndex["model"]["url"] = f"model://{modelPath.name}"
    oldIndex["universes"]["4"]["url"] = "db://old.sqlite"
    newIndex["model"]["url"] = f"model://{modelPath.name}"
    newIndex["universes"]["4"]["url"] = "db://new.sqlite"
    return {
        "old": oldIndex,
        "new": newIndex,
        "payloads": payloads,
        "modelBytes": modelPath.read_bytes(),
    }


def makeGateway(simulated: SimulatedGithub) -> HttpAssetGateway:
    return HttpAssetGateway(
        indexUrl="index://latest/index.json", transport=simulated.transport
    )


def test_first_run_bootstraps_model_and_database(tmp_path, published):
    simulated = SimulatedGithub(
        "index://latest/index.json", published["new"], published["payloads"]
    )
    paths = FakePaths(tmp_path)
    reporter = FakeReporter()
    ready = []
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=paths,
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=reporter,
        onStoreReady=ready.append,
    )
    controller.refresh()
    assert paths.modelPath().is_file()
    assert paths.databasePath("4").is_file()
    assert ready, "onStoreReady must fire after bootstrap"
    assert ready[0].buildStamp() == "20261029T120000Z"
    assert ready[0].universe() == "4"
    assert any("first run" in message.lower() for message in reporter.infos)


def test_up_to_date_cache_is_not_downloaded_again(tmp_path, published):
    simulated = SimulatedGithub(
        "index://latest/index.json", published["new"], published["payloads"]
    )
    paths = FakePaths(tmp_path)
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=paths,
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=FakeReporter(),
        onStoreReady=lambda store: None,
    )
    controller.refresh()  # bootstrap
    simulated.downloads.clear()
    controller.refresh()  # second open, nothing newer
    assert simulated.downloads == [], "no download expected when cache is current"
    assert paths.modelPath().read_bytes() == published["modelBytes"]


def test_newer_build_replaces_the_cached_database(tmp_path, published):
    simulated = SimulatedGithub(
        "index://latest/index.json", published["old"], published["payloads"]
    )
    paths = FakePaths(tmp_path)
    ready = []
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=paths,
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=FakeReporter(),
        onStoreReady=ready.append,
    )
    controller.refresh()  # bootstrap with the old build
    assert ready[-1].buildStamp() == "20261001T000000Z"

    simulated.index = published["new"]  # a newer build gets published
    controller.refresh()
    assert ready[-1].buildStamp() == "20261029T120000Z"
    assert any("updating" in message.lower() for message in reporterOf(controller).infos)


def reporterOf(controller: AssetsController) -> FakeReporter:
    return controller.reporter  # type: ignore[return-value]


def test_offline_falls_back_to_the_cache(tmp_path, published):
    simulated = SimulatedGithub(
        "index://latest/index.json", published["new"], published["payloads"]
    )
    paths = FakePaths(tmp_path)
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=paths,
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=FakeReporter(),
        onStoreReady=lambda store: None,
    )
    controller.refresh()  # bootstrap while online
    cachedBytes = paths.databasePath("4").read_bytes()

    simulated.failOnUrl = "index://latest/index.json"  # offline
    controller.refresh()
    assert controller.reporter.warnings, "offline refresh must warn"
    assert paths.databasePath("4").read_bytes() == cachedBytes
    store = SqliteVectorStore.open(paths.databasePath("4"))
    assert store.pluginCount() == len(FIXTURE_PLUGINS)


def test_no_database_for_the_running_universe_is_reported(tmp_path, published):
    index = json.loads(json.dumps(published["new"]))
    del index["universes"]["4"]  # only QGIS 3 was published
    simulated = SimulatedGithub("index://latest/index.json", index, published["payloads"])
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=FakePaths(tmp_path),
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=FakeReporter(),
        onStoreReady=lambda store: None,
    )
    controller.refresh()
    assert any("no published database" in message.lower() for message in controller.reporter.errors)


def test_corrupt_database_download_is_rejected_and_cache_survives(tmp_path, published):
    payloads = dict(published["payloads"])
    payloads["db://corrupt.sqlite"] = b"not a database"
    goodIndex = published["old"]
    corruptIndex = json.loads(json.dumps(published["new"]))
    # Break the checksum: the gateway must refuse the file.
    corruptIndex["universes"]["4"]["url"] = "db://corrupt.sqlite"
    corruptIndex["universes"]["4"]["sha256"] = "0" * 64
    simulated = SimulatedGithub(
        "index://latest/index.json", goodIndex, payloads
    )
    paths = FakePaths(tmp_path)
    controller = AssetsController(
        gateway=makeGateway(simulated),
        paths=paths,
        versionProvider=FakeVersionProvider("4"),
        runner=InlineRunner(),
        reporter=FakeReporter(),
        onStoreReady=lambda store: None,
    )
    controller.refresh()  # bootstrap with a good build
    assert paths.databasePath("4").is_file()
    goodBytes = paths.databasePath("4").read_bytes()

    simulated.index = corruptIndex  # a corrupt update gets published
    controller.refresh()
    assert controller.reporter.errors, "checksum mismatch must be reported"
    assert paths.databasePath("4").read_bytes() == goodBytes, (
        "a failed update must leave the previous cache untouched"
    )
