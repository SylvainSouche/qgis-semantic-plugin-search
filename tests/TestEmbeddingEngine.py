"""Tokenizer and embedding engine behavior (t-engine-embedding)."""
from __future__ import annotations

import numpy as np
import pytest

from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine
from tests.conftest import buildFixtureVectors, fixtureTokenizer


@pytest.fixture()
def engine(modelPath) -> StaticEmbeddingEngine:
    model = NpzStaticModel.load(modelPath)
    return StaticEmbeddingEngine(fixtureTokenizer(), model)


def test_wordpiece_tokenizes_known_words():
    tokens = fixtureTokenizer().tokenize("Digitize Parcel Boundaries")
    assert "parcel" in tokens
    assert "boundaries" in tokens
    assert all(token == token.lower() for token in tokens)


def test_wordpiece_splits_punctuation():
    tokens = fixtureTokenizer().tokenize("wfs, wms; api.")
    assert "wfs" in tokens and "wms" in tokens and "api" in tokens
    assert "," in tokens and ";" in tokens


def test_wordpiece_uses_continuation_pieces():
    # "layers" is in the vocabulary, but "unwanted" is not: it must become
    # [UNK] rather than raising or disappearing.
    tokens = fixtureTokenizer().tokenize("layers unwanted")
    assert "layers" in tokens
    assert "[UNK]" in tokens


def test_wordpiece_handles_accents_and_case():
    tokens = fixtureTokenizer().tokenize("PARCÉL")
    assert tokens == ["parcel"]


def test_embedding_is_deterministic(engine):
    first = engine.embedQuery("digitize parcel boundaries")
    second = engine.embedQuery("digitize parcel boundaries")
    np.testing.assert_array_equal(first, second)


def test_embedding_is_normalized(engine):
    vector = engine.embedQuery("digitize parcel boundaries from a drone orthophoto")
    assert vector.shape == (8,)
    assert vector.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vector), 1.0, rtol=1e-5)


def test_embedding_ignores_out_of_vocabulary_queries(engine):
    vector = engine.embedQuery("completely unknown zzzz qqqq")
    assert not np.any(vector)


def test_embedding_of_empty_query_is_zero(engine):
    assert not np.any(engine.embedQuery(""))


def test_embedding_points_to_the_right_cluster(engine):
    parcelVector = engine.embedQuery("digitize parcel boundaries cadastre")
    invoiceVector = engine.embedQuery("invoice accounting budget report")
    vocabulary, vectors = buildFixtureVectors()
    geoAxis = vectors[vocabulary["parcel"]].copy()  # axis 0 carries the cluster
    geoAxis[4:] = 0.0
    officeAxis = np.zeros_like(geoAxis)
    officeAxis[2] = 1.0
    assert float(parcelVector @ geoAxis) > float(parcelVector @ officeAxis)
    assert float(invoiceVector @ officeAxis) > float(invoiceVector @ geoAxis)
