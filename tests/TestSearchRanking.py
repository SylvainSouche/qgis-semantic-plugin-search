"""Search ranking against a store built by the real pipeline
(t-search-rank, req-cosine-ranking).
"""
from __future__ import annotations

import numpy as np
import pytest

from SemanticPluginSearch.Data.SqliteVectorStore import SqliteVectorStore
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine
from SemanticPluginSearch.Domain.SearchEngine import SearchService
from pipeline.BuildEmbeddings import EmbeddingDatabaseWriter
from pipeline.PluginCatalogue import parseCatalogue
from tests.conftest import FIXTURE_PLUGINS, fixtureTokenizer


@pytest.fixture()
def store(modelPath, catalogueAndReadmes, tmp_path):
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
    return SqliteVectorStore.open(database)


@pytest.fixture()
def searchService(modelPath):
    model = NpzStaticModel.load(modelPath)
    engine = StaticEmbeddingEngine(fixtureTokenizer(), model)
    return SearchService(engine)


def test_all_fixture_plugins_are_indexed(store):
    assert store.pluginCount() == len(FIXTURE_PLUGINS)
    assert store.universe() == "4"
    assert store.modelId() == "fixture-static-model"
    assert store.buildStamp() == "20261029T120000Z"


def test_store_vectors_are_normalized(store):
    norms = np.linalg.norm(store.embeddings(), axis=1)
    nonzero = norms[norms > 0]
    np.testing.assert_allclose(nonzero, 1.0, rtol=1e-5)


def test_geo_query_ranks_parcel_plugin_first(store, searchService):
    results = searchService.search(
        store, "digitize parcel boundaries from a drone orthophoto of cadastre lots"
    )
    assert results, "expected matches for a geo query"
    assert results[0].info.name == "ParcelDigitizer"


def test_office_query_ranks_invoice_plugin_first(store, searchService):
    results = searchService.search(store, "invoice accounting budget report export")
    assert results[0].info.name == "InvoiceReporter"


def test_ml_query_ranks_classifier_plugin_first(store, searchService):
    results = searchService.search(
        store, "classify imagery with machine learning models and training"
    )
    assert results[0].info.name == "OrthoClassifier"


def test_scores_are_cosine_similarities(store, searchService):
    results = searchService.search(store, "digitize parcel boundaries")
    query = searchService.engine.embedQuery("digitize parcel boundaries")
    expected = float(store.embeddings()[store.pluginIds().index(results[0].info.pluginId)] @ query)
    assert results[0].score == pytest.approx(expected, abs=1e-6)
    assert all(
        results[i].score >= results[i + 1].score for i in range(len(results) - 1)
    )


def test_unknown_vocabulary_query_yields_no_results(store, searchService):
    assert searchService.search(store, "zzzz qqqq wwww") == []


def test_limit_and_metadata_roundtrip(store, searchService):
    results = searchService.search(store, "parcel invoice wfs layer", limit=2)
    assert len(results) <= 2
    info = results[0].info
    original = FIXTURE_PLUGINS[info.pluginId]
    assert info.description == original["description"]
    assert info.author == "Fixture Author"
    assert "parcel" in info.tags or info.name == "InvoiceReporter" or info.name == "WebLayerLoader"


def test_filter_results_is_a_pure_domain_function(store, searchService):
    from SemanticPluginSearch.Domain.SearchEngine import filterResults

    results = searchService.search(store, "invoice export report budget")
    assert {r.info.name for r in results} >= {"InvoiceReporter", "ShapeExporter"}
    standard = filterResults(results)
    assert all(
        not r.info.experimental and not r.info.deprecated for r in standard
    ), "default filters drop flagged plugins"
    withExperimental = filterResults(results, includeExperimental=True)
    assert any(r.info.experimental for r in withExperimental)
    withDeprecated = filterResults(results, includeDeprecated=True)
    assert any(r.info.deprecated for r in withDeprecated)
    withBoth = filterResults(results, True, True)
    assert len(withBoth) == len(results)


def test_flagged_plugins_are_indexed_with_their_flags(store):
    invoice = store.pluginInfo(3)
    assert invoice.experimental is True and invoice.deprecated is False
    exporter = store.pluginInfo(5)
    assert exporter.deprecated is True and exporter.experimental is False


def test_search_survives_a_dimension_mismatch(store):
    """C1: an engine answering with the wrong dimension yields no results,
    never a crash (model still downloading on first run)."""
    from SemanticPluginSearch.Domain.SearchEngine import SearchService

    class MismatchEngine:
        def embedQuery(self, text):  # noqa: ANN001, ANN202
            return np.zeros(1, dtype=np.float32)

    assert SearchService(MismatchEngine()).search(store, "parcel") == []
