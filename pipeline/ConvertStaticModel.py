"""Convert a model2vec style static model into the distributed .npz format.

Input: a directory holding a model2vec model (model.safetensors with the
"embeddings" tensor and tokenizer.json with the WordPiece vocabulary), or a
minishlab potion-* release. Only commercially usable models may be converted
for distribution (see the license policy in the project model).

Usage:
    python pipeline/ConvertStaticModel.py \
        --model-dir model/potion-base-8M \
        --model-id static-potion-base-8M \
        --output model/EmbeddingModel.npz
"""
from __future__ import annotations

# @impl 0f87-6ae3-6996-571d

import json
import struct
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from SemanticPluginSearch.Data.StaticModelLoader import (  # noqa: E402
    FORMAT_ID,
    KEY_META,
    KEY_TOKENS,
    KEY_VECTORS,
    TOKENIZER_ID,
)


def readSafetensorsTensor(path: Path, tensorName: str) -> np.ndarray:
    """Read one tensor from a safetensors file without extra dependencies."""
    with path.open("rb") as stream:
        (headerLength,) = struct.unpack("<Q", stream.read(8))
        header = json.loads(stream.read(headerLength))
        if tensorName not in header:
            raise KeyError(
                f"tensor {tensorName!r} not found; available: {sorted(header)}"
            )
        entry = header[tensorName]
        start, end = entry["data_offsets"]
        stream.seek(8 + headerLength + start)
        payload = stream.read(end - start)
    dtype = {
        "F32": np.float32,
        "F16": np.float16,
        "BF16": None,
        "I64": np.int64,
        "I32": np.int32,
    }.get(entry["dtype"])
    if dtype is None:
        raise ValueError(f"unsupported safetensors dtype: {entry['dtype']}")
    return np.frombuffer(payload, dtype=dtype).reshape(entry["shape"])


def readWordPieceVocab(tokenizerJsonPath: Path) -> dict[str, int]:
    document = json.loads(tokenizerJsonPath.read_text(encoding="utf-8"))
    vocab = document["model"]["vocab"]
    return {token: int(index) for token, index in vocab.items()}


def writeNpz(
    outputPath: Path,
    vocab: dict[str, int],
    vectors: np.ndarray,
    modelId: str,
    dim: int,
    licenseNote: str,
    sourceModel: str,
) -> None:
    order = sorted(vocab.items(), key=lambda item: item[1])
    tokens = np.array([token for token, _ in order], dtype=np.str_)
    matrix = np.zeros((len(tokens), dim), dtype=np.float16)
    for position, (_, index) in enumerate(order):
        if index < len(vectors):
            matrix[position] = vectors[index]
    meta = json.dumps(
        {
            "format": FORMAT_ID,
            "tokenizer": TOKENIZER_ID,
            "model_id": modelId,
            "dim": dim,
            "license": licenseNote,
            "source_model": sourceModel,
        }
    )
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        outputPath,
        **{KEY_TOKENS: tokens, KEY_VECTORS: matrix, KEY_META: np.array(meta)},
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Directory with model.safetensors and tokenizer.json",
    )
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--license-note",
        default="Commercial use allowed; see source model license",
    )
    parser.add_argument("--source-model", default="")
    args = parser.parse_args(argv)

    modelDir = Path(args.model_dir)
    vectors = readSafetensorsTensor(modelDir / "model.safetensors", "embeddings")
    vocab = readWordPieceVocab(modelDir / "tokenizer.json")
    writeNpz(
        outputPath=Path(args.output),
        vocab=vocab,
        vectors=vectors,
        modelId=args.model_id,
        dim=int(vectors.shape[1]),
        licenseNote=args.license_note,
        sourceModel=args.source_model,
    )
    print(f"Wrote {args.output}: {len(vocab)} tokens, dim {vectors.shape[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
