"""Query embedding: token vectors looked up and mean pooled locally.

The engine is the plugin side of the static embedding approach: it never
talks to a network and never leaves the user machine. It consumes a
StaticModelData port so the storage format stays out of the domain.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import numpy as np

from .Ports import EmbeddingEngine, StaticModelData
from .WordPieceTokenizer import WordPieceTokenizer


class StaticEmbeddingEngine(EmbeddingEngine):
    """Embeds a query by averaging the vectors of its known tokens."""

    def __init__(self, tokenizer: WordPieceTokenizer, model: StaticModelData) -> None:
        self.tokenizer = tokenizer
        self.model = model

    def embedQuery(self, text: str) -> np.ndarray:
        """Return the normalized query embedding, or a zero vector when empty.

        A zero vector (no token of the input carries meaning) yields no
        matches rather than an arbitrary ranking; callers treat it as
        "no results". A query made only of unknown tokens also returns a
        zero vector: [UNK] is a placeholder, not a meaning.
        """
        tokens = self.tokenizer.tokenize(text)
        # [UNK] is a placeholder, not a meaning: exclude it from the average.
        meaningful = [token for token in tokens if token != self.tokenizer.unkToken]
        if not meaningful:
            return np.zeros(self.model.dimension(), dtype=np.float32)
        tokenIds = [self.model.tokenId(token) for token in meaningful]
        stacked = np.stack(
            [self.model.vectorFor(tokenId) for tokenId in tokenIds if tokenId is not None]
        )
        mean = stacked.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            return np.zeros_like(mean)
        return (mean / norm).astype(np.float32)

# @impl 0f87-6ae3-6985-7c77
