"""Encoding of plugin vectors in the embeddings database.

Two formats, named by the meta key `vector_format`:

- float32 (the key is absent): each blob is the vector as little endian
  float32. Every released plugin version reads this one.
- int8-scaled: each blob is one little endian float32 scale followed by the
  vector as int8, value = int8 * scale. A quarter of the size; the search
  quality evaluation measured no loss (docs/SearchQualityEvaluation.md).

Decoded rows are L2 normalised again, so a cosine is still one matrix
product whatever the format.

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import numpy as np

VECTOR_FORMAT_KEY = "vector_format"
FLOAT32 = "float32"
INT8_SCALED = "int8-scaled"
SUPPORTED_FORMATS = (FLOAT32, INT8_SCALED)


class VectorFormatError(ValueError):
    """A stored vector does not match the declared format."""


def encodeInt8(vector: np.ndarray) -> bytes:
    """Encode one vector as a float32 scale followed by int8 values."""
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    peak = float(np.abs(vector).max()) if vector.size else 0.0
    scale = peak / 127.0 if peak > 0 else 1.0
    values = np.clip(np.round(vector / scale), -127, 127).astype(np.int8)
    return np.float32(scale).astype("<f4").tobytes() + values.tobytes()


def decodeVector(blob: bytes, dim: int, vectorFormat: str = FLOAT32) -> np.ndarray:
    """Decode one stored blob into a float32 vector of width dim."""
    if vectorFormat == FLOAT32:
        if len(blob) != 4 * dim:
            raise VectorFormatError(f"float32 vector of {len(blob)} bytes, expected {4 * dim}")
        return np.frombuffer(blob, dtype="<f4").astype(np.float32)
    if vectorFormat == INT8_SCALED:
        if len(blob) != 4 + dim:
            raise VectorFormatError(f"int8 vector of {len(blob)} bytes, expected {4 + dim}")
        scale = float(np.frombuffer(blob[:4], dtype="<f4")[0])
        return np.frombuffer(blob[4:], dtype=np.int8).astype(np.float32) * scale
    raise VectorFormatError(f"unsupported vector format: {vectorFormat!r}")


def normaliseRows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return (matrix / np.where(norms > 0, norms, 1.0)).astype(np.float32)
