"""Build the index.json describing the stored embeddings.

The index is the only file the plugin fetches first: it names the model and
the per universe databases with checksums, sizes and build stamps, so the
plugin can decide whether its cache is stale and verify what it downloads.
pipeline/StoreEmbeddings.py writes it into the embeddings branch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

INDEX_FORMAT = "qgis-semantic-search-index-v1"


def sha256Of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def databaseMeta(path: Path) -> dict:
    import sqlite3

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        meta = dict(connection.execute("SELECT key, value FROM meta"))
    finally:
        connection.close()
    return {
        "build_stamp": meta.get("build_stamp", ""),
        "plugin_count": int(meta.get("plugin_count", "0")),
        "universe": meta.get("universe", ""),
        "model_id": meta.get("model_id", ""),
    }


def modelMeta(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as archive:
        meta = json.loads(str(archive["meta"]))
    return {
        "model_id": meta.get("model_id", "unknown"),
        "dim": int(meta.get("dim", 0)),
        "format": meta.get("format", ""),
        "tokenizer": meta.get("tokenizer", ""),
        "license": meta.get("license", ""),
        "source_model": meta.get("source_model", ""),
    }


def buildIndex(
    modelPath: Path,
    databases: dict[str, Path],
    baseUrl: str,
    generatedAt: str,
) -> dict:
    """Build the index for the given model and universe databases."""
    index = {
        "format": INDEX_FORMAT,
        "generated_at": generatedAt,
        "model": {
            "url": f"{baseUrl}/{modelPath.name}",
            "sha256": sha256Of(modelPath),
            "bytes": modelPath.stat().st_size,
            **modelMeta(modelPath),
        },
        "universes": {},
    }
    for universe, databasePath in sorted(databases.items()):
        meta = databaseMeta(databasePath)
        index["universes"][universe] = {
            "url": f"{baseUrl}/{databasePath.name}",
            "sha256": sha256Of(databasePath),
            "bytes": databasePath.stat().st_size,
            "build_stamp": meta["build_stamp"],
            "plugin_count": meta["plugin_count"],
        }
    return index


# @impl 0f87-6ae3-6986-d290
