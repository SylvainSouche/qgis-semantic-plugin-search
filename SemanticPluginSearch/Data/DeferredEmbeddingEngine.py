"""EmbeddingEngine that loads the cached model on first use.

Until the model file exists (first run bootstrap), queries yield a zero
vector sized to the store dimension, which the search reports as no
results. The expected dimension is provided when the store becomes ready
so the zero vector always matches the database.

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import numpy as np

from ..Domain.Ports import PathsProvider


class DeferredEmbeddingEngine:
    """Loads the cached model lazily; safe to query before it exists."""

    def __init__(self, paths: PathsProvider) -> None:
        self.paths = paths
        self.engine = None
        self._expectedDimension = 0

    def setExpectedDimension(self, dimension: int) -> None:
        """Size the placeholder vectors to the store dimension."""
        self._expectedDimension = int(dimension)

    def modelId(self) -> str | None:
        """The loaded model id, or None while nothing is loaded."""
        return self.engine.modelId() if self.engine is not None else None

    def reset(self) -> None:
        """Drop the loaded model so the next query reloads the file."""
        self.engine = None

    def ensureLoaded(self) -> bool:
        if self.engine is not None:
            return True
        modelPath = self.paths.modelPath()
        if not modelPath.is_file():
            return False
        from .StaticModelLoader import NpzStaticModel
        from ..Domain.EmbeddingEngine import StaticEmbeddingEngine
        from ..Domain.WordPieceTokenizer import WordPieceTokenizer

        model = NpzStaticModel.load(modelPath)
        self.engine = StaticEmbeddingEngine(WordPieceTokenizer(model.vocabulary()), model)
        return True

    def validatePairing(self, store) -> None:  # noqa: ANN001 - PluginVectorStore
        """Load the model and make sure it can rank the store; raise if not.

        A model loaded earlier but different from the store's (the model was
        updated) is dropped and the file on disk reloaded once. Runs on a
        worker thread: parsing the model must never freeze the window.
        """
        if not self.ensureLoaded():
            return  # no model yet: queries stay empty until it is downloaded
        if self.modelId() == store.modelId():
            return
        self.reset()
        self.ensureLoaded()
        if self.modelId() != store.modelId():
            raise RuntimeError(
                f"model {self.modelId()!r} cannot rank database {store.modelId()!r}"
            )

    def embedQuery(self, text: str) -> np.ndarray:
        if not self.ensureLoaded():
            return np.zeros(self._expectedDimension or 1, dtype=np.float32)
        return self.engine.embedQuery(text)
# @impl 4be9-6ae4-3eac-c78b
