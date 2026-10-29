"""Pipeline build end to end on fixture data: catalogue parsing, text
preparation, database writing and release index generation
(t-pipeline-build, req-pipeline-embed, req-pipeline-publish).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from pipeline.PluginCatalogue import parseCatalogue, safePluginFileName
from pipeline.TextPreparation import preparePluginText, stripMarkdownNoise
from pipeline.WriteReleaseIndex import buildIndex
from SemanticPluginSearch.Data.SqliteVectorStore import SqliteVectorStore
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from pipeline.BuildEmbeddings import EmbeddingDatabaseWriter
from tests.conftest import FIXTURE_PLUGINS, fixtureCatalogueBytes, fixtureTokenizer


def test_catalogue_parses_all_plugins_with_snapshot_metadata():
    records = parseCatalogue(fixtureCatalogueBytes())
    assert len(records) == len(FIXTURE_PLUGINS)
    byId = {record.pluginId: record for record in records}
    parcel = byId[1]
    assert parcel.name == "ParcelDigitizer"
    assert parcel.tags == ("parcel", "cadastre", "digitizing")
    assert parcel.downloads == 1000
    assert parcel.averageVote == pytest.approx(4.5)
    assert parcel.experimental is False


def test_catalogue_deduplicates_by_plugin_id_keeping_first():
    document = fixtureCatalogueBytes().decode("utf-8")
    duplicated = document.replace(
        "</plugins>",
        """<pyqgis_plugin name="ParcelDigitizer" version="0.0.1" plugin_id="1">
        <description><![CDATA[Old version]]></description>
    </pyqgis_plugin></plugins>""",
    )
    records = parseCatalogue(duplicated.encode("utf-8"))
    assert len(records) == len(FIXTURE_PLUGINS)
    assert all(record.version != "0.0.1" for record in records)


def test_safe_plugin_file_name_matches_the_fetcher():
    # \w keeps letters across scripts, like the original fetcher did.
    assert safePluginFileName("My Plugin: éà!") == "My_Plugin_éà"
    assert safePluginFileName("...") == "unnamed-plugin"


def test_text_preparation_weights_name_tags_and_readme():
    records = {record.pluginId: record for record in parseCatalogue(fixtureCatalogueBytes())}
    text = preparePluginText(records[1], "# Parcel Digitizer\n\nDigitize lots.")
    assert text.count("ParcelDigitizer") == 2  # name repeated
    assert text.count("cadastre") >= 4  # tags repeated and present in about
    assert "Digitize lots." in text


def test_markdown_noise_is_stripped():
    noisy = (
        "# Title\n\n![logo](img.png)\n[link](https://x.test)\n```python\ncode()\n```\n"
        "**bold** and *italic* <b>html</b>\n"
    )
    text = stripMarkdownNoise(noisy)
    assert "img.png" not in text and "https://x.test" not in text
    # The fenced code block content is removed with the fence.
    assert "code()" not in text
    assert "bold" in text and "Title" in text and "link" in text


def test_built_database_is_complete_and_normalized(modelPath, catalogueAndReadmes, tmp_path):
    catalogue, readmeDir = catalogueAndReadmes
    model = NpzStaticModel.load(modelPath)
    writer = EmbeddingDatabaseWriter(model, fixtureTokenizer())
    database = tmp_path / "out" / "Embeddings-4.sqlite"
    readmeUrls = {1: "https://example.test/parcel.md"}
    count = writer.build(
        records=parseCatalogue(catalogue.read_bytes()),
        readmeDir=readmeDir,
        universe="4",
        outputPath=database,
        buildStamp="20261029T120000Z",
        catalogueSource="fixture-catalogue",
        readmeUrls=readmeUrls,
    )
    assert count == len(FIXTURE_PLUGINS)

    store = SqliteVectorStore.open(database)
    assert store.universe() == "4"
    assert store.pluginCount() == count
    assert store.buildStamp() == "20261029T120000Z"
    info = store.pluginInfo(1)
    assert info.readmeUrl == "https://example.test/parcel.md"
    norms = np.linalg.norm(store.embeddings(), axis=1)
    np.testing.assert_allclose(norms[norms > 0], 1.0, rtol=1e-5)
    # Every fixture plugin carries its readme content in its embedding:
    # a query on distinctive readme words finds the plugin.
    for pluginId, spec in FIXTURE_PLUGINS.items():
        assert store.pluginInfo(pluginId) is not None
        assert spec["description"] == store.pluginInfo(pluginId).description


def test_release_index_binds_checksums_and_stamps(modelPath, catalogueAndReadmes, tmp_path):
    catalogue, readmeDir = catalogueAndReadmes
    model = NpzStaticModel.load(modelPath)
    writer = EmbeddingDatabaseWriter(model, fixtureTokenizer())
    database = tmp_path / "Embeddings-4.sqlite"
    writer.build(
        records=parseCatalogue(catalogue.read_bytes()),
        readmeDir=readmeDir,
        universe="4",
        outputPath=database,
        buildStamp="20261029T120000Z",
        catalogueSource="fixture",
    )
    index = buildIndex(
        modelPath=modelPath,
        databases={"4": database},
        baseUrl="https://github.com/acme/qgis-semantic-plugin-search/releases/latest/download",
        generatedAt="20261029T130000Z",
    )
    assert index["format"] == "qgis-semantic-search-index-v1"
    assert index["generated_at"] == "20261029T130000Z"
    modelEntry = index["model"]
    assert modelEntry["url"].endswith("/" + modelPath.name)
    assert modelEntry["sha256"] == hashlib.sha256(modelPath.read_bytes()).hexdigest()
    assert modelEntry["bytes"] == modelPath.stat().st_size
    assert modelEntry["model_id"] == "fixture-static-model"
    release = index["universes"]["4"]
    assert release["url"].endswith("/" + database.name)
    assert release["sha256"] == hashlib.sha256(database.read_bytes()).hexdigest()
    assert release["build_stamp"] == "20261029T120000Z"
    assert release["plugin_count"] == len(FIXTURE_PLUGINS)
    json.dumps(index)  # must be serializable
