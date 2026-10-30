# Semantic Plugin Search — Developer guide

How the plugin and its GitHub pipeline work, how to build, test and release
them, and where the specification lives. For using the plugin, see the
[user guide](UserGuide.md).

## Overview

Two parts share one vector space:

- **the plugin** (`SemanticPluginSearch/`) ranks the whole QGIS plugin
  universe against the user's description, shows details, and hands every
  install, upgrade, reinstall or uninstall to the standard plugin manager;
- **the pipeline** (`pipeline/`, run weekly by GitHub Actions) downloads the
  official plugin catalogue and every readme, embeds them, and publishes the
  databases, the model and an index to the fixed `embeddings` release.

```
GitHub release "embeddings"                    QGIS
┌──────────────────────────┐   index check   ┌─────────────────────────────┐
│ index.json               │◀────────────────│ AssetsController            │
│ EmbeddingModel.npz ~17MB │──── download ──▶│  verified cache in profile  │
│ Embeddings-3.sqlite      │                 │ SearchController            │
│ Embeddings-4.sqlite      │                 │  query → embed → hybrid rank│
└──────────────────────────┘                 │ DetailsController           │
        ▲                                    │  metadata now, readme async │
        │ weekly BuildEmbeddings action      │ IconController              │
        │  FetchCatalogue.py                 │  one batched job per search │
        │  BuildEmbeddings.py                │ ActionController            │
        │  WriteReleaseIndex.py, PublishGate │  installed state from disk  │
        └──────────────────────────          │  → pyplugin_installer       │
                                             └─────────────────────────────┘
```

### Embeddings

The model is a **static token embedding** (model2vec style):
[minishlab/potion-base-8M](https://huggingface.co/minishlab/potion-base-8M),
MIT licensed and distilled from the Apache-2.0 all-MiniLM-L6-v2, converted
into a plain float16 matrix of token vectors (`.npz`, about 17 MB, 29528
tokens × 256 dimensions). The revision and file checksum are pinned.

Plugin side, a query is tokenized by a pure-Python BERT WordPiece tokenizer,
its token vectors are looked up and mean-pooled with numpy, and the result
is normalized. There is no torch, no onnxruntime and nothing to compile. The
pipeline uses the same tokenizer and pooling code, so queries and plugins
live in the same space.

### Ranking

`Domain/SearchEngine.py` scores every plugin with a **hybrid score**:

- the cosine similarity between the query vector and the plugin vector
  (embedded from name, description, about, tags and a capped readme
  excerpt);
- plus a bounded **lexical boost** (`Domain/LexicalBoost.py`): +0.30 when
  the whole query equals the plugin name (ignoring case, spaces and
  punctuation), plus 0.20 / 0.10 / 0.05 times the share of query words found
  in the name / tags / description. Word forms match by prefix when the
  shorter covers at least 70% of the longer (digitize matches digitizer).

The lexical index is an inverted index built once per database. A query
over the 1567 plugins of QGIS 4.2 takes about 1 to 6 ms. The percentage
shown is the hybrid score, capped at 100.

### Installed state

`Data/InstalledPlugins.py` reads `metadata.txt` from each folder in
`qgis.utils.plugin_paths`. QGIS's own in-memory lists are not used, because
they are keyed differently and are never cleaned up on uninstall.
`Domain/Installed.py` matches a result by installer key (derived from the
package file name), then case-insensitively, then by declared name, and
derives the action buttons and badges. The state is re-read after every
action.

### Networking

Inside QGIS every download goes through `QgisBridge/NetworkTransport.py`
(`QgsBlockingNetworkRequest`), so proxy, SSL and authentication settings
apply, and the QGIS network cache is bypassed. The Data layer gateways
receive that function as their transport. The pipeline uses
`pipeline/HttpTransport.py` (urllib) instead, and tests use in-memory
fixtures.

## Code layout and rules

| Path | Role |
|---|---|
| `SemanticPluginSearch/Domain/` | Pure logic: entities, ports, tokenizer, engine, hybrid ranking, installed state |
| `SemanticPluginSearch/Data/` | SQLite store, model loader, verified downloads, installed plugin scan |
| `SemanticPluginSearch/Controllers/` | Qt-free orchestration: search, details, icons, assets, actions |
| `SemanticPluginSearch/Presentation/` | Qt widgets: search window, metadata and readme tabs |
| `SemanticPluginSearch/QgisBridge/` | The only QGIS-aware code: paths, settings, message bar, network, installer, threads |
| `pipeline/` | GitHub side: fetch, embed, convert model, write index, publish gate |
| `tools/` | Headless smoke test inside a real QGIS |
| `tests/` | Functional suite, runs without QGIS |
| `project-model/` | Requirements, decisions, use cases and their links to code |
| `docs/` | User guide, this guide, and the generated specification |

These rules are enforced by tests, not by convention:

- `Domain`, `Data` and `Controllers` import neither qgis nor Qt, and their
  only third-party import is numpy (`TestArchitecture`);
- the query path imports no network module, so the raw query cannot leave
  the machine (`TestArchitecture`);
- every Qt and QGIS enum is used in its scoped form, so one codebase runs on
  PyQt5 (QGIS 3) and PyQt6 (QGIS 4) (`TestArchitecture`);
- every relative import resolves (`TestPluginImports`), and every private
  attribute a class reads is defined (`TestSelfAttributes`);
- the plugin folder meets the QGIS plugin repository rules
  (`TestPluginRepositoryRules`).

Naming is CamelCase: UpperCamelCase classes and modules, Qt-style camelCase
methods.

## Working on it

```bash
make help        # targets, variables and install instructions
make test        # pytest suite, no QGIS needed (ARGS="-k ranking" to filter)
make smoke       # load and exercise the plugin headless in every installed QGIS
make fetch       # catalogue and readmes into data/ (QGIS_VERSIONS="3.44 4.2")
make embed       # model and per-universe databases into build/, fetching first if needed
make package     # run the tests, then build dist/SemanticPluginSearch.<version>.zip
make clean       # remove build/, dist/ and caches; keeps data/ and .venv/
make clean-all   # also remove data/ and .venv/
```

`make test` creates `.venv` with numpy and pytest on first use. CI runs the
suite and ruff on Python 3.9 and 3.12.

`make smoke` boots each QGIS found in `/Applications` with its own Python,
offscreen, and checks that the plugin imports, reports through the real
message bar, builds its window, searches, fetches icons through the QGIS
network stack (again on a repeated search), and reads the installed plugins
from disk. Set `SMOKE_DB` to an embeddings database to include the real
search checks.

To try a working copy in QGIS, copy or symlink `SemanticPluginSearch/` into
the profile's `python/plugins/` folder, or install the zip from `make
package`.

## The pipeline

`.github/workflows/BuildEmbeddings.yml` runs on a schedule: Monday 03:00 UTC
builds QGIS 3.44, Tuesday builds QGIS 4.2, and a manual run builds both. Each
run:

1. converts the pinned static model;
2. fetches the catalogue and readmes for the scheduled universes;
3. builds each embeddings database;
4. writes `index.json`, merging in the universes it did not rebuild from the
   previous index;
5. refuses to publish if a universe has no plugins, or its plugin count
   moved by more than 10% from the previous release (`PublishGate.py`);
6. uploads the binaries to the `embeddings` release, then the index last.

The plugin reads `releases/download/embeddings/index.json`, a fixed tag, so
another release marked *Latest* cannot break the update channel.

## Releasing the plugin

1. Bump `version` in `SemanticPluginSearch/metadata.txt` and add a
   `changelog` line that starts with that version.
2. `make package`, which refuses to package if a test fails.
3. `make smoke` on QGIS 3 and QGIS 4.
4. Upload the zip to plugins.qgis.org. The repository rules (mandatory
   metadata, LICENSE in the package, no binaries, QGIS network stack, Qt6
   compatibility) are checked by `TestPluginRepositoryRules`. The upload is
   also scanned with bandit, flake8 and detect-secrets, and the current code
   has no critical finding.

## Specification

Requirements, decisions, use cases and their links to code live in
`project-model/` and follow the discovery-driven development method: every
object is written through `model.py`, never by hand. Start from
`project-model/index.md`. `docs/Specification.md` is generated from it.
Regenerate it rather than editing it.

## License

MIT, see [LICENSE](../LICENSE). It is compatible with the GPLv2-or-later
requirement for QGIS plugins, and the complete source is published here.
QGIS plugin manager internals are GPL; the plugin calls them, it does not
include them.
