"""Model and database pairing (DeferredEmbeddingEngine.validatePairing).

Regression: QGIS reported "The embedding model does not match the
embeddings database ... 'StaticEmbeddingEngine' object has no attribute
'modelId'" on every database update, so search never activated once a
model was loaded. The pairing check lived in PluginEntry, which the suite
cannot import, and the fakes all had a modelId. It now runs here with the
real model loader, engine and database.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pipeline.BuildEmbeddings import EmbeddingDatabaseWriter
from pipeline.PluginCatalogue import parseCatalogue
from SemanticPluginSearch.Data.DeferredEmbeddingEngine import DeferredEmbeddingEngine
from SemanticPluginSearch.Data.SqliteVectorStore import SqliteVectorStore
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine
from SemanticPluginSearch.Domain.SearchEngine import SearchService
from tests.conftest import fixtureTokenizer


class Paths:
    def __init__(self, model: Path) -> None:
        self.model = model

    def modelPath(self) -> Path:
        return self.model


@pytest.fixture()
def store(modelPath, catalogueAndReadmes, tmp_path):
    catalogue, readmeDir = catalogueAndReadmes
    database = tmp_path / "Embeddings-4.sqlite"
    EmbeddingDatabaseWriter(NpzStaticModel.load(modelPath), fixtureTokenizer()).build(
        records=parseCatalogue(catalogue.read_bytes()),
        readmeDir=readmeDir,
        universe="4",
        outputPath=database,
        buildStamp="20261030T000000Z",
        catalogueSource="fixture",
    )
    return SqliteVectorStore.open(database)


def test_the_real_engine_reports_its_model_id(modelPath):
    model = NpzStaticModel.load(modelPath)
    engine = StaticEmbeddingEngine(fixtureTokenizer(), model)
    assert engine.modelId() == model.modelId() == "fixture-static-model"


def test_a_matching_model_validates_and_the_search_runs(modelPath, store, tmp_path):
    cached = tmp_path / "cache" / "EmbeddingModel.npz"
    cached.parent.mkdir()
    shutil.copyfile(modelPath, cached)
    engine = DeferredEmbeddingEngine(Paths(cached))
    engine.validatePairing(store)
    assert engine.modelId() == store.modelId()
    assert SearchService(engine).search(store, "parcel cadastre")


def test_validating_twice_reuses_the_loaded_model(modelPath, store):
    engine = DeferredEmbeddingEngine(Paths(modelPath))
    engine.validatePairing(store)
    loaded = engine.engine
    engine.validatePairing(store)
    assert engine.engine is loaded


def test_no_model_yet_is_not_an_error(store, tmp_path):
    engine = DeferredEmbeddingEngine(Paths(tmp_path / "missing.npz"))
    engine.validatePairing(store)
    assert engine.modelId() is None
    assert not np.any(engine.embedQuery("parcel"))


def test_a_different_model_is_refused(modelPath):
    engine = DeferredEmbeddingEngine(Paths(modelPath))
    other = SimpleNamespace(modelId=lambda: "another-model")
    with pytest.raises(RuntimeError, match="cannot rank"):
        engine.validatePairing(other)
