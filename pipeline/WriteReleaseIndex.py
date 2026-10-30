"""Write the release index.json describing published assets.

The index is the only file the plugin fetches first: it names the model and
the per universe databases with checksums, sizes and build stamps, so the
plugin can decide whether its cache is stale and verify what it downloads.

Usage:
    python pipeline/WriteReleaseIndex.py \
        --model build/EmbeddingModel.npz \
        --database 3=build/Embeddings-3.sqlite \
        --database 4=build/Embeddings-4.sqlite \
        --base-url https://github.com/OWNER/REPO/releases/latest/download \
        --output build/index.json
"""
from __future__ import annotations

import hashlib
import json
import sys
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


def previousUniverses(previousUrl: str, transport=None) -> dict[str, dict]:
    """Load the universe entries of the previously published index.

    Returns an empty dict when there is no previous release or it cannot be
    reached: a first publish has nothing to merge.
    """
    if not previousUrl:
        return {}
    try:
        import json

        fetch = transport
        if fetch is None:
            from pipeline.HttpTransport import fetchUrl

            fetch = fetchUrl
        document = json.loads(fetch(previousUrl))
        return document.get("universes") or {}
    except Exception:  # noqa: BLE001 - merging is best effort
        return {}


def buildIndex(
    modelPath: Path,
    databases: dict[str, Path],
    baseUrl: str,
    generatedAt: str,
    previousUniversesMap: dict[str, dict] | None = None,
) -> dict:
    """Build the index for the freshly built universes.

    Universes of the previous release that were NOT rebuilt this run are
    carried over verbatim: their assets are still published under the same
    fixed tag and their checksums still match, so the index stays complete
    when the weekly builds are spread across days.
    """
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
    for universe, entry in sorted((previousUniversesMap or {}).items()):
        if universe not in index["universes"]:
            index["universes"][universe] = entry
    return index


def main(argv: list[str] | None = None) -> int:
    import argparse

    import datetime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--database", action="append", required=True, help="Universe=path")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--merge-previous-url",
        default="",
        help="Published index whose unbuilt universes are carried over",
    )
    args = parser.parse_args(argv)

    databases = {}
    for entry in args.database:
        universe, _, path = entry.partition("=")
        databases[universe.strip()] = Path(path.strip())
    index = buildIndex(
        modelPath=Path(args.model),
        databases=databases,
        baseUrl=args.base_url.rstrip("/"),
        generatedAt=datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ"),
    )
    outputPath = Path(args.output)
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    outputPath.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Wrote {outputPath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 0f87-6ae3-6986-d290
