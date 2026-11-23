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
4. writes an int8 copy of every database (pipeline/QuantizeDatabase.py),
   listed under universes_q8 for the plugin versions that read it, while
   universes keeps the float32 files every released version reads;
5. writes index.json and deletes every data file of its variant it no
   longer references, keeping the readme caches the fetch step maintains.

Variants: the branch holds one data set per search model, side by side.
The default variant (index.json, EmbeddingModel.<hash>.npz,
Embeddings-<universe>.<hash>.sqlite) keeps serving potion-base-8M to the
released plugin versions up to 0.4.8; the "ml" variant (index-ml.json,
EmbeddingModel-ml.<hash>.npz, Embeddings-ml-<universe>.<hash>.sqlite)
serves the multilingual model to the versions that read index-ml.json. A
run of one variant never touches the other's files.

Everything is local: no network access, no release API.

Usage:
    python pipeline/StoreEmbeddings.py --store store \
        --database 4=build/Embeddings-4.sqlite \
        [--model build/EmbeddingModel.npz] [--variant ml] \
        --base-url https://raw.githubusercontent.com/OWNER/REPO/embeddings
"""
from __future__ import annotations

import datetime
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.PublishGate import checkGates  # noqa: E402
from pipeline.QuantizeDatabase import quantizeDatabase  # noqa: E402
from pipeline.WriteReleaseIndex import (  # noqa: E402
    buildIndex,
    databaseMeta,
    modelMeta,
    sha256Of,
)

# Only files named like a variant's own data are ever deleted, so the
# README, the readme caches (Readmes-<universe>.json.gz, shared by every
# variant) and the other variant's files always survive a run.


class GateFailure(RuntimeError):
    """The new build looks broken; the store was left untouched."""


def contentName(path: Path, stem: str) -> str:
    return f"{stem}.{sha256Of(path)[:12]}{path.suffix}"


def variantSuffix(variant: str) -> str:
    if variant and not re.fullmatch(r"[a-z0-9]+", variant):
        raise ValueError(f"variant must be lowercase letters and digits: {variant!r}")
    return f"-{variant}" if variant else ""


def indexName(variant: str = "") -> str:
    return f"index{variantSuffix(variant)}.json"


def ownsFile(name: str, variant: str = "") -> bool:
    """Whether a store file belongs to this variant's data set."""
    suffix = re.escape(variantSuffix(variant))
    pattern = (rf"EmbeddingModel{suffix}\.[0-9a-f]{{12}}\.npz"
               rf"|\.?Embeddings{suffix}-\d+(?:-q8)?(?:\.[0-9a-f]{{12}})?\.sqlite")
    return re.fullmatch(pattern, name) is not None


def storeEmbeddings(
    store: Path,
    freshDatabases: dict[str, Path],
    baseUrl: str,
    model: Path | None = None,
    generatedAt: str | None = None,
    variant: str = "",
) -> dict:
    """Update the store and return the written index; raise GateFailure."""
    store.mkdir(parents=True, exist_ok=True)
    suffix = variantSuffix(variant)
    indexPath = store / indexName(variant)
    previous = json.loads(indexPath.read_text(encoding="utf-8")) if indexPath.is_file() else {}
    baseUrl = baseUrl.rstrip("/")

    if model is not None:
        modelPath = store / contentName(model, f"EmbeddingModel{suffix}")
        if not modelPath.is_file():
            shutil.copyfile(model, modelPath)
    else:
        previousModel = (previous.get("model") or {}).get("url", "")
        modelPath = store / previousModel.rsplit("/", 1)[-1] if previousModel else None
        if modelPath is None or not modelPath.is_file():
            raise GateFailure("no model given and none stored: pass --model to bootstrap")

    modelId = modelMeta(modelPath)["model_id"]
    databases: dict[str, Path] = {}
    for universe, entry in (previous.get("universes") or {}).items():
        carried = store / entry.get("url", "").rsplit("/", 1)[-1]
        if universe not in freshDatabases and carried.is_file():
            databases[universe] = carried
    for universe, path in {**databases, **freshDatabases}.items():
        built = databaseMeta(path)["model_id"]
        if built != modelId:
            raise GateFailure(
                f"QGIS {universe} database was built with {built!r}, not with the stored"
                f" model {modelId!r}: rebuild every universe when the model changes")
    staged: list[Path] = []
    for universe, source in freshDatabases.items():
        target = store / contentName(source, f"Embeddings{suffix}-{universe}")
        if not target.is_file():
            shutil.copyfile(source, target)
            staged.append(target)
        databases[universe] = target

    quantized: dict[str, Path] = {}
    previousQuantized = previous.get("universes_q8") or {}
    for universe, source in databases.items():
        carried = store / (previousQuantized.get(universe) or {}).get("url", "").rsplit("/", 1)[-1]
        if universe not in freshDatabases and carried.is_file() and carried.suffix == ".sqlite":
            quantized[universe] = carried
            continue
        temporary = quantizeDatabase(source, store / f".Embeddings{suffix}-{universe}-q8.sqlite")
        target = store / contentName(temporary, f"Embeddings{suffix}-{universe}-q8")
        if target.is_file():
            temporary.unlink()
        else:
            temporary.replace(target)
            staged.append(target)
        quantized[universe] = target

    index = buildIndex(
        modelPath=modelPath,
        databases=databases,
        quantized=quantized,
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
    referenced = ({modelPath.name} | {path.name for path in databases.values()}
                  | {path.name for path in quantized.values()})
    for path in store.iterdir():
        if path.is_file() and path.name not in referenced and ownsFile(path.name, variant):
            path.unlink()
    return index


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="Working tree of the data branch")
    parser.add_argument("--database", action="append", default=[], help="Universe=path")
    parser.add_argument("--model", default="", help="Model to store (bootstrap or change)")
    parser.add_argument("--base-url", required=True, help="Raw URL of the data branch")
    parser.add_argument("--variant", default="", help="Data set suffix, e.g. ml (default: none)")
    args = parser.parse_args(argv)

    fresh = {}
    for entry in args.database:
        universe, _, path = entry.partition("=")
        fresh[universe.strip()] = Path(path.strip())
    try:
        index = storeEmbeddings(
            Path(args.store), fresh, args.base_url, Path(args.model) if args.model else None,
            variant=args.variant,
        )
    except GateFailure as failure:
        print(f"Not stored: {failure}", file=sys.stderr)
        return 1
    for universe, entry in sorted(index["universes"].items()):
        print(f"{indexName(args.variant)} QGIS {universe}: {entry['plugin_count']} plugins,"
              f" {entry['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# @impl 4be9-6ae3-f849-7641
# @impl 4be9-6ae4-3a55-8652
