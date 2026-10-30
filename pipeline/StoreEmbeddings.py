"""Store freshly built embeddings in the data branch working tree.

The CI checks out the `embeddings` branch into a directory, builds one or
more universe databases, and calls this script, which:

1. copies each fresh database (and the model, when given) into the store
   under a content addressed name, e.g. Embeddings-4.1a2b3c4d5e6f.sqlite,
   so a cached index can never pair with a different file of the same name;
2. keeps the universes that were not rebuilt this run, as referenced by the
   store's current index.json;
3. refuses to store anything when a universe has no plugins or its plugin
   count moved more than the gate tolerance from the stored one;
4. writes index.json and deletes every data file it no longer references,
   keeping the readme caches the fetch step maintains.

Everything is local: no network access, no release API.

Usage:
    python pipeline/StoreEmbeddings.py --store store \
        --database 4=build/Embeddings-4.sqlite \
        [--model build/EmbeddingModel.npz] \
        --base-url https://raw.githubusercontent.com/OWNER/REPO/embeddings
"""
from __future__ import annotations

import datetime
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.PublishGate import checkGates  # noqa: E402
from pipeline.WriteReleaseIndex import buildIndex, sha256Of  # noqa: E402

INDEX_NAME = "index.json"
KEEP_NAMES = {INDEX_NAME, "README.md"}
# Per universe readme caches (pipeline/FetchCatalogue.py ReadmeCache): kept
# on the branch for the next run, never listed in the index.
KEEP_PATTERNS = ("Readmes-*.json.gz",)


class GateFailure(RuntimeError):
    """The new build looks broken; the store was left untouched."""


def contentName(path: Path, stem: str) -> str:
    return f"{stem}.{sha256Of(path)[:12]}{path.suffix}"


def storeEmbeddings(
    store: Path,
    freshDatabases: dict[str, Path],
    baseUrl: str,
    model: Path | None = None,
    generatedAt: str | None = None,
) -> dict:
    """Update the store and return the written index; raise GateFailure."""
    store.mkdir(parents=True, exist_ok=True)
    indexPath = store / INDEX_NAME
    previous = json.loads(indexPath.read_text(encoding="utf-8")) if indexPath.is_file() else {}
    baseUrl = baseUrl.rstrip("/")

    if model is not None:
        modelPath = store / contentName(model, "EmbeddingModel")
        if not modelPath.is_file():
            shutil.copyfile(model, modelPath)
    else:
        previousModel = (previous.get("model") or {}).get("url", "")
        modelPath = store / previousModel.rsplit("/", 1)[-1] if previousModel else None
        if modelPath is None or not modelPath.is_file():
            raise GateFailure("no model given and none stored: pass --model to bootstrap")

    databases: dict[str, Path] = {}
    for universe, entry in (previous.get("universes") or {}).items():
        carried = store / entry.get("url", "").rsplit("/", 1)[-1]
        if universe not in freshDatabases and carried.is_file():
            databases[universe] = carried
    staged: list[Path] = []
    for universe, source in freshDatabases.items():
        target = store / contentName(source, f"Embeddings-{universe}")
        if not target.is_file():
            shutil.copyfile(source, target)
            staged.append(target)
        databases[universe] = target

    index = buildIndex(
        modelPath=modelPath,
        databases=databases,
        baseUrl=baseUrl,
        generatedAt=generatedAt
        or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    previousCounts = {
        universe: int(entry.get("plugin_count", 0))
        for universe, entry in (previous.get("universes") or {}).items()
    } or None
    violations = checkGates(index, previousCounts)
    if violations:
        for path in staged:
            path.unlink()
        raise GateFailure("; ".join(violations))

    indexPath.write_text(json.dumps(index, indent=2), encoding="utf-8")
    referenced = {modelPath.name} | {path.name for path in databases.values()}
    for path in store.iterdir():
        if not path.is_file() or path.name in referenced | KEEP_NAMES:
            continue
        if any(path.match(pattern) for pattern in KEEP_PATTERNS):
            continue
        path.unlink()
    return index


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="Working tree of the data branch")
    parser.add_argument("--database", action="append", default=[], help="Universe=path")
    parser.add_argument("--model", default="", help="Model to store (bootstrap or change)")
    parser.add_argument("--base-url", required=True, help="Raw URL of the data branch")
    args = parser.parse_args(argv)

    fresh = {}
    for entry in args.database:
        universe, _, path = entry.partition("=")
        fresh[universe.strip()] = Path(path.strip())
    try:
        index = storeEmbeddings(
            Path(args.store), fresh, args.base_url, Path(args.model) if args.model else None
        )
    except GateFailure as failure:
        print(f"Not stored: {failure}", file=sys.stderr)
        return 1
    for universe, entry in sorted(index["universes"].items()):
        print(f"QGIS {universe}: {entry['plugin_count']} plugins, {entry['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# @impl 4be9-6ae3-f849-7641
# @impl 4be9-6ae4-3a55-8652
