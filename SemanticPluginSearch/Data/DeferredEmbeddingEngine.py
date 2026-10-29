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

    def embedQuery(self, text: str) -> np.ndarray:
        if not self.ensureLoaded():
            return np.zeros(self._expectedDimension or 1, dtype=np.float32)
        return self.engine.embedQuery(text)
