"""int8 storage of plugin vectors and of the model's token table."""
from __future__ import annotations

import json

import numpy as np
import pytest

from SemanticPluginSearch.Data.AssetGateways import parseIndexDocument
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from SemanticPluginSearch.Data.VectorCodec import (
    INT8_SCALED,
    VectorFormatError,
    decodeVector,
    encodeInt8,
)
from pipeline.ConvertStaticModel import writeNpz


def testInt8RoundTripKeepsTheDirection():
    rng = np.random.default_rng(1)
    vector = rng.normal(size=256).astype(np.float32)
    decoded = decodeVector(encodeInt8(vector), 256, INT8_SCALED)
    assert len(encodeInt8(vector)) == 4 + 256
    cosine = vector @ decoded / np.linalg.norm(vector) / np.linalg.norm(decoded)
    assert cosine > 0.9999
    assert not np.any(decodeVector(encodeInt8(np.zeros(4)), 4, INT8_SCALED))


def testWrongSizesAndFormatsAreRefused():
    with pytest.raises(VectorFormatError):
        decodeVector(b"\\0" * 10, 4)
    with pytest.raises(VectorFormatError):
        decodeVector(b"\\0" * 8, 4, INT8_SCALED)
    with pytest.raises(VectorFormatError):
        decodeVector(b"", 0, "int4")


def testInt8ModelLoadsScaledAndOldReadersSeeTheSameDirections(tmp_path):
    rng = np.random.default_rng(2)
    vectors = rng.normal(size=(5, 8)).astype(np.float32)
    path = tmp_path / "model.npz"
    writeNpz(path, {f"t{i}": i for i in range(5)}, vectors, "m", 8, "MIT", "src")
    model = NpzStaticModel.load(path)
    assert np.allclose(model.vectors(), vectors, atol=float(np.abs(vectors).max()) / 127)
    with np.load(path) as archive:
        assert archive["vectors"].dtype == np.int8
        assert json.loads(str(archive["meta"]))["dtype"] == "int8"
        raw = archive["vectors"].astype(np.float32)  # what released plugin versions do
    old, new = raw[[0, 2, 3]].mean(axis=0), model.vectors()[[0, 2, 3]].mean(axis=0)
    assert old @ new / np.linalg.norm(old) / np.linalg.norm(new) == pytest.approx(1.0, abs=1e-6)


def testTheIndexPrefersTheInt8Databases():
    entry = {"url": "u", "sha256": "s", "bytes": 1, "build_stamp": "b", "plugin_count": 2}
    document = {"format": "qgis-semantic-search-index-v1", "model": {},
                "universes": {"3": {**entry, "url": "plain"}},
                "universes_q8": {"3": {**entry, "url": "small"}}}
    assert parseIndexDocument(document).universes["3"].database.url == "small"
    del document["universes_q8"]
    assert parseIndexDocument(document).universes["3"].database.url == "plain"
