"""Static model persistence in the distributed .npz format.

The format is intentionally minimal: a string array of vocabulary tokens, a
float16 matrix of token vectors aligned with it, and a JSON metadata blob.
It carries no code and is loaded with numpy only.

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..Domain.Ports import StaticModelData

FORMAT_ID = "static-token-embeddings-v1"
TOKENIZER_ID = "bert-wordpiece-uncased"
KEY_TOKENS = "tokens"
KEY_VECTORS = "vectors"
KEY_META = "meta"


class StaticModelFormatError(ValueError):
    """The model file does not match the expected format."""


class NpzStaticModel(StaticModelData):
    """In memory view of a loaded .npz static model."""

    def __init__(
        self,
        vocabulary: dict[str, int],
        vectors: np.ndarray,
        modelId: str,
        tokenizerId: str,
    ) -> None:
        self._vocabulary = vocabulary
        self._vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._modelId = modelId
        self._tokenizerId = tokenizerId

    @staticmethod
    def load(path: Path) -> NpzStaticModel:
        """Load and validate a model file, converting vectors to float32."""
        with np.load(path, allow_pickle=False) as archive:
            try:
                tokens = archive[KEY_TOKENS]
                vectors = archive[KEY_VECTORS]
                meta = json.loads(str(archive[KEY_META]))
            except KeyError as error:
                raise StaticModelFormatError(f"missing array: {error}") from error
        if meta.get("format") != FORMAT_ID:
            raise StaticModelFormatError(
                f"unsupported model format: {meta.get('format')!r}"
            )
        if len(tokens) != len(vectors):
            raise StaticModelFormatError(
                f"vocabulary size {len(tokens)} does not match {len(vectors)} vectors"
            )
        vocabulary = {token: index for index, token in enumerate(tokens.tolist())}
        vectors = vectors.astype(np.float32)
        if vectors.ndim != 2:
            raise StaticModelFormatError("vectors must be a two dimensional matrix")
        return NpzStaticModel(
            vocabulary=vocabulary,
            vectors=vectors,
            modelId=str(meta.get("model_id", "unknown")),
            tokenizerId=str(meta.get("tokenizer", TOKENIZER_ID)),
        )

    def tokenId(self, token: str) -> int | None:
        return self._vocabulary.get(token)

    def vectorFor(self, tokenId: int) -> np.ndarray:
        return self._vectors[tokenId]

    def dimension(self) -> int:
        return int(self._vectors.shape[1])

    def modelId(self) -> str:
        return self._modelId

    def tokenizerId(self) -> str:
        return self._tokenizerId

    def vocabulary(self) -> dict[str, int]:
        return self._vocabulary

    def vectors(self) -> np.ndarray:
        return self._vectors
