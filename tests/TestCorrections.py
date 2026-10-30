"""Regression tests for the review corrections: dimension safety (C1),
UNK pooling consistency (C2), download caps (C5) and stamp comparison (C6).
"""

import numpy as np
import pytest

from SemanticPluginSearch.Data.AssetGateways import RemoteFile, TransportError
from SemanticPluginSearch.Data.AssetGateways import _VerifiedDownloader
from SemanticPluginSearch.Data.DeferredEmbeddingEngine import DeferredEmbeddingEngine
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine
from SemanticPluginSearch.Controllers.AssetsController import _stampIsNewer
from tests.conftest import fixtureTokenizer


class StubPaths:
    def __init__(self, root) -> None:  # noqa: ANN001
        self.root = root

    def cacheDir(self):  # noqa: ANN202
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def modelPath(self):  # noqa: ANN202
        return self.cacheDir() / "EmbeddingModel.npz"

    def databasePath(self, universe):  # noqa: ANN002, ANN202
        return self.cacheDir() / f"Embeddings-{universe}.sqlite"


def test_deferred_engine_zero_vector_matches_expected_dimension(tmp_path):
    engine = DeferredEmbeddingEngine(StubPaths(tmp_path))
    assert engine.embedQuery("parcel").shape == (1,)  # no hint yet
    engine.setExpectedDimension(256)
    vector = engine.embedQuery("parcel")
    assert vector.shape == (256,)
    assert not np.any(vector)
    assert not engine.ensureLoaded(), "no model file in the stub paths"


def test_deferred_engine_loads_the_model_when_present(tmp_path, modelPath):
    import shutil

    paths = StubPaths(tmp_path)
    shutil.copy(modelPath, paths.modelPath())
    engine = DeferredEmbeddingEngine(paths)
    vector = engine.embedQuery("digitize parcel boundaries")
    assert vector.shape == (8,)
    np.testing.assert_allclose(np.linalg.norm(vector), 1.0, rtol=1e-5)


def test_unk_tokens_do_not_pollute_the_average(modelPath):
    model = NpzStaticModel.load(modelPath)
    engine = StaticEmbeddingEngine(fixtureTokenizer(), model)
    withUnk = engine.embedQuery("parcel unwanted zzzz")
    clean = engine.embedQuery("parcel")
    np.testing.assert_allclose(withUnk, clean, rtol=1e-5)


def test_verified_downloader_enforces_a_size_cap(tmp_path):
    downloader = _VerifiedDownloader(
        transport=lambda url, maxBytes=None: b"x" * 60, maxBytes=50
    )
    remote = RemoteFile(url="https://x.test/big.npz", sha256="", bytes=0)
    with pytest.raises(TransportError, match="too large"):
        downloader.downloadVerified(remote, tmp_path / "out.npz")


def test_stamp_comparison_prefers_parsed_timestamps():
    assert _stampIsNewer("20261029T183649Z", "20261029T190000Z") is True
    assert _stampIsNewer("20261029T190000Z", "20261029T183649Z") is False
    assert _stampIsNewer("20261029T183649Z", "20261029T183649Z") is False
    # Unparseable stamps fall back to the lexicographic order.
    assert _stampIsNewer("abc", "abd") is True
