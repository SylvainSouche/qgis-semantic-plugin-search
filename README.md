# QGIS Semantic Plugin Search

Find QGIS plugins by describing what you want in plain language —
*"classify a drone orthophoto into land cover classes"*, *"create contour
lines from a DEM"* — instead of guessing the keyword a plugin author chose.

A QGIS plugin (Python) plus a GitHub side pipeline:

- the **plugin** ranks the whole QGIS plugin universe against your query
  using text embeddings, shows results on the left and plugin metadata /
  readme on the right, and defers Install / Upgrade / Reinstall / Uninstall
  to the standard plugin manager;
- the **pipeline** (GitHub Actions, weekly) downloads the official plugin
  catalogue and every plugin readme, computes the embeddings for the QGIS 3
  and QGIS 4 plugin universes, and publishes the databases to the project
  releases with an index the plugin checks for updates.

Your query never leaves your machine: the query embedding is computed
in-process from a small cached model.

## How it works

```
GitHub releases                                QGIS
┌──────────────────────────┐   index check   ┌────────────────────────────┐
│ index.json               │◀────────────────│ AssetsController           │
│ EmbeddingModel.npz (17MB)│──── download ──▶│  cache in profile dir      │
│ Embeddings-3.sqlite      │                 │ SearchController           │
│ Embeddings-4.sqlite      │                 │  query → engine → rank     │
└──────────────────────────┘                 │  ~1ms per 1500 plugins     │
        ▲                                    │ DetailsController          │
        │ weekly Action:                     │  metadata now, readme async│
│ FetchCatalogue.py │                        │ ActionController            │
│ BuildEmbeddings.py│                         │  → pyplugin_installer      │
│ WriteReleaseIndex.py                       └────────────────────────────┘
└──────────────────────────┘
```

The embedding model is a **static token embedding** (model2vec style):
GitHub-side, an Apache-2.0 / MIT sentence transformer is distilled into a
plain matrix of token vectors (`.npz`, float16, ~17MB for 29528 tokens ×
256 dims). Plugin-side, a query is tokenized with a pure-Python BERT
WordPiece tokenizer, vectors are looked up and mean-pooled with numpy.
No torch, no onnxruntime, nothing to compile — just numpy, which QGIS
already bundles. The same tokenizer and pooling run in the pipeline, so
queries and plugins live in the same vector space.

## Repository layout

| Path | Role |
|---|---|
| `SemanticPluginSearch/` | The QGIS plugin (deployable folder) |
| `SemanticPluginSearch/Domain/` | Pure logic: entities, ports, tokenizer, engine, ranking |
| `SemanticPluginSearch/Data/` | SQLite store, npz model loader, verified downloads |
| `SemanticPluginSearch/Controllers/` | Qt-free orchestration (search, details, assets, actions) |
| `SemanticPluginSearch/Presentation/` | Qt widgets: search window, two tabs, action buttons |
| `SemanticPluginSearch/QgisBridge/` | The only QGIS-aware code: paths, message bar, installer delegation, threading |
| `pipeline/` | GitHub side: fetch catalogue/readmes, build embeddings, convert model, write index |
| `.github/workflows/` | Weekly `BuildEmbeddings` + `Tests` |
| `tests/` | Full functional suite, runs without QGIS (46 tests) |
| `project-model/` | Discovery-driven development model: requirements, decisions, tests, links (see `project-model/index.md`) |
| `data/` | Downloaded catalogues and readmes (local, git-ignored) — the seed and fixture source for the pipeline |

## Strict MVC

The import rules are enforced by `tests/TestArchitecture.py`, not by
convention:

- `Domain`, `Data` and `Controllers` import **neither qgis nor Qt**; their
  only third-party dependency is numpy;
- the query processing layers import **no network module at all** — the raw
  query text cannot leave the machine;
- `Presentation` (views) contains no business logic; controllers drive views
  through structural protocols (`Controllers/ViewPorts.py`) so both sides
  are tested with fakes;
- all Qt imports go through `qgis.PyQt`, with the `QAction` QtGui/QtWidgets
  shim, so one codebase serves PyQt5 (QGIS 3.44) and PyQt6 (QGIS 4.x).

## Install (development)

Copy (or symlink) `SemanticPluginSearch/` into your QGIS profile plugin
directory and enable it:

```
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/        (Linux)
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/  (macOS)
C:\Users\<you>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\ (Windows)
```

On first open the plugin downloads the model (~17MB) and the embeddings
database (~5MB) from the project's GitHub release into
`<profile>/semantic-search/`, then works offline. The index location is
overridable in QSettings: `/SemanticPluginSearch/embeddings/indexUrl`.

The plugin defaults to the project repository
`github.com/SylvainSouche/qgis-semantic-plugin-search`: the index URL points
at that repository's `releases/latest/download/index.json`. Until the first
embeddings release is published there (run the `BuildEmbeddings` workflow or
`make fetch` + `make embed`), the plugin will report that it cannot reach the
index and work from the cache.

## Build the embeddings yourself

```bash
# One-time: convert a commercially usable static model (MIT/Apache-2.0!)
python pipeline/ConvertStaticModel.py \
    --model-dir /path/to/potion-base-8M \
    --model-id static-potion-base-8M \
    --output model/EmbeddingModel.npz

# Per universe (the CI workflow does this weekly)
python pipeline/FetchCatalogue.py 4.2 --output-dir build
python pipeline/BuildEmbeddings.py \
    --catalogue build/plugins-4.2.xml --readmes build/plugins-4.2 \
    --readme-urls build/readme-urls-4.2.json \
    --model model/EmbeddingModel.npz --universe 4 \
    --output build/Embeddings-4.sqlite
python pipeline/WriteReleaseIndex.py --model model/EmbeddingModel.npz \
    --database 4=build/Embeddings-4.sqlite \
    --base-url https://github.com/SylvainSouche/qgis-semantic-plugin-search/releases/latest/download \
    --output build/index.json
```

Real-world reference point: the full QGIS 4.2 universe (1567 plugins with
readmes) embeds in **~4.6s** on a laptop CPU; a query ranks all of them in
**~0.2ms**.

## License policy

The repository and the plugin are released under the **MIT license** (see
[LICENSE](LICENSE)). One caveat to keep in mind before publishing to
plugins.qgis.org: the plugin delegates install actions to QGIS's
`pyplugin_installer` (GPL) and runs inside GPL QGIS — the QGIS ecosystem
commonly expects plugins to remain GPL-compatible even when their own source
is MIT. The choice is yours; the repository source itself carries no
restriction.

Only models whose license allows commercial use may be converted and
distributed — a database of vectors is close enough to model weights that
the distinction does not matter. The CI pipeline uses
`minishlab/potion-base-8M` (MIT, distilled from `all-MiniLM-L6-v2`,
Apache-2.0). Non-commercial models are allowed **only** as unpublished
development fixtures. The license note travels inside the model file and in
the release index.

## Make targets

```text
make help          # targets, variables and install instructions
make test          # pytest suite, no QGIS needed (ARGS="-k ranking" to filter)
make fetch         # catalogue + readmes into data/ (QGIS_VERSIONS=3.44 4.2)
make embed         # per universe databases into build/; fetches first if needed
make package       # dist/SemanticPluginSearch.<version>.zip, installable in QGIS
make clean         # remove build/, dist/ and caches; keeps data/ and .venv/
make clean-all     # also remove data/ and .venv/
```

`data/` (downloaded metadata and readmes), `build/` (embeddings databases and
converted model) and `dist/` are generated content and git-ignored.

## Development

```bash
python3.12 -m venv .venv && .venv/bin/pip install numpy pytest
.venv/bin/python -m pytest
```

The suite covers the full functional scope without QGIS: ranking,
embedding, database build, asset update flow (bootstrap, stale check,
offline fallback, checksum rejection with atomic replace), details
orchestration with stale-fetch dropping, action delegation, pipeline build
and the architecture scans.

## Specification & status

Requirements, decisions, use cases and their links to code live in
`project-model/` (regenerate views with the discovery-driven-dev tooling;
start from `project-model/index.md`). Current honest state:

- all 19 leaf requirements have implementations; 45 tests pass;
- Qt views and the `pyplugin_installer` delegation are written but only
  verifiable inside QGIS (assumption `asm-installer-reachable` in the
  model); a first in-QGIS pass is the next step;
- the static-embedding engine choice (`ai-static-embeddings`) and a few
  naming/licensing defaults await your confirmation — swap points are the
  `EmbeddingEngine` port and `QgisBridge/Settings.py`.
