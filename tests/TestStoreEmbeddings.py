"""Storing embeddings in the data branch (pipeline/StoreEmbeddings.py).

The CI fetches, embeds and stores, nothing more: no release API, no network
in this step. Fresh databases land under content addressed names, universes
not rebuilt this run are carried over from the stored index, a broken build
is refused without touching the store, and unreferenced files are pruned.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pipeline.BuildEmbeddings import EmbeddingDatabaseWriter
from pipeline.PluginCatalogue import parseCatalogue
from pipeline.StoreEmbeddings import GateFailure, storeEmbeddings
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel
from tests.conftest import fixtureTokenizer

BASE = "https://raw.githubusercontent.com/acme/repo/embeddings"


@pytest.fixture()
def buildDatabase(modelPath, catalogueAndReadmes, tmp_path):
    catalogue, readmeDir = catalogueAndReadmes

    def build(universe: str, stamp: str, keep: int | None = None) -> Path:
        records = parseCatalogue(catalogue.read_bytes())[:keep]
        output = tmp_path / "build" / f"{stamp}" / f"Embeddings-{universe}.sqlite"
        output.parent.mkdir(parents=True, exist_ok=True)
        EmbeddingDatabaseWriter(NpzStaticModel.load(modelPath), fixtureTokenizer()).build(
            records=records,
            readmeDir=readmeDir,
            universe=universe,
            outputPath=output,
            buildStamp=stamp,
            catalogueSource="fixture",
        )
        return output

    return build


def stored(store: Path) -> set[str]:
    return {path.name for path in store.iterdir()}


def test_first_store_needs_and_keeps_the_model(tmp_path, modelPath, buildDatabase):
    store = tmp_path / "store"
    with pytest.raises(GateFailure, match="bootstrap"):
        storeEmbeddings(store, {"4": buildDatabase("4", "20261029T000000Z")}, BASE)
    index = storeEmbeddings(
        store, {"4": buildDatabase("4", "20261029T000000Z")}, BASE, model=modelPath
    )
    assert index["model"]["url"].startswith(BASE + "/EmbeddingModel.")
    name = index["universes"]["4"]["url"].rsplit("/", 1)[-1]
    assert name.startswith("Embeddings-4.") and name.endswith(".sqlite")
    assert stored(store) == {"index.json", name, index["model"]["url"].rsplit("/", 1)[-1]}


def test_universes_not_rebuilt_are_carried_over(tmp_path, modelPath, buildDatabase):
    store = tmp_path / "store"
    storeEmbeddings(
        store,
        {"3": buildDatabase("3", "20261026T000000Z"), "4": buildDatabase("4", "20261027T000000Z")},
        BASE,
        model=modelPath,
    )
    first = json.loads((store / "index.json").read_text())
    index = storeEmbeddings(store, {"3": buildDatabase("3", "20261102T000000Z")}, BASE)
    assert index["universes"]["4"] == first["universes"]["4"], "QGIS 4 untouched"
    assert index["universes"]["3"]["build_stamp"] == "20261102T000000Z"
    assert index["model"] == first["model"], "the stored model is reused"
    old3 = first["universes"]["3"]["url"].rsplit("/", 1)[-1]
    assert old3 not in stored(store), "the replaced database is pruned"


def test_a_collapsed_build_is_refused_and_the_store_untouched(tmp_path, modelPath, buildDatabase):
    store = tmp_path / "store"
    storeEmbeddings(store, {"4": buildDatabase("4", "20261027T000000Z")}, BASE, model=modelPath)
    before = {path.name: path.read_bytes() for path in store.iterdir()}
    broken = buildDatabase("4", "20261103T000000Z", keep=1)
    with pytest.raises(GateFailure, match="deviates"):
        storeEmbeddings(store, {"4": broken}, BASE)
    assert {path.name: path.read_bytes() for path in store.iterdir()} == before


def test_the_readme_survives_pruning(tmp_path, modelPath, buildDatabase):
    store = tmp_path / "store"
    store.mkdir()
    (store / "README.md").write_text("data branch")
    (store / "stale.bin").write_bytes(b"old")
    storeEmbeddings(store, {"4": buildDatabase("4", "20261027T000000Z")}, BASE, model=modelPath)
    assert "README.md" in stored(store) and "stale.bin" not in stored(store)
    shutil.rmtree(store)


def test_readme_caches_are_kept_but_not_indexed(tmp_path, modelPath, buildDatabase):
    store = tmp_path / "store"
    store.mkdir()
    (store / "Readmes-4.json.gz").write_bytes(b"cache")
    index = storeEmbeddings(
        store, {"4": buildDatabase("4", "20261027T000000Z")}, BASE, model=modelPath
    )
    assert (store / "Readmes-4.json.gz").read_bytes() == b"cache"
    assert "Readmes" not in json.dumps(index)
