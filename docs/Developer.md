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
  official plugin catalogue and every readme, embeds them, and stores the
  databases, the model and an index on the `embeddings` branch.

```
branch "embeddings"                            QGIS
┌──────────────────────────┐   index check   ┌─────────────────────────────┐
│ index.json               │◀────────────────│ AssetsController            │
│ EmbeddingModel.<h>.npz   │──── download ──▶│  verified cache in profile  │
│ Embeddings-3.<h>.sqlite  │                 │ SearchController            │
│ Embeddings-4.<h>.sqlite  │                 │  query → embed → hybrid rank│
└──────────────────────────┘                 │ DetailsController           │
        ▲                                    │  metadata now, readme async │
        │ weekly BuildEmbeddings action      │ IconController              │
        │  FetchCatalogue.py                 │  one batched job per search │
        │  BuildEmbeddings.py                │ ActionController            │
        │  StoreEmbeddings.py                │  installed state from disk  │
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
receive that function as their transport, and tests use in-memory
fixtures. The pipeline has its own urllib transport in
`pipeline/FetchCatalogue.py`, with a byte cap and a wall clock deadline per
download.

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

Errors always reach the user in a popup: anything reported through
`Reporter.error` opens a non-blocking error dialog (and is kept in the
message bar), and failures that QGIS's plugin installer only logs are
captured during the call and reported the same way. Warnings, such as an
offline update check, stay in the message bar.

Naming is CamelCase: UpperCamelCase classes and modules, Qt-style camelCase
methods.

## Working on it

```bash
make help        # targets, variables and install instructions
make test        # pytest suite, no QGIS needed (ARGS="-k ranking" to filter)
make smoke       # load and exercise the plugin headless in every installed QGIS
make fetch       # catalogue and readmes into data/ (QGIS_VERSIONS="3.44 4.2")
make embed       # model and per-universe databases into build/, fetching first if needed
make dist        # package checks (standard library only, no venv), then dist/SemanticPluginSearch.<version>.zip
make version VERSION=0.4.1 COMMENT="What changed"   # set the version and its changelog entry
make increment INC=rel COMMENT="What changed"       # bump maj, min or rel (0.4.0 -> 1.0.0, 0.5.0, 0.4.1)
make clean       # remove build/ (except build/ddd), dist/ and caches; keeps data/ and .venv/
make clean-all   # also remove data/ and .venv/
```

`make test`, `fetch` and `embed` create `.venv` with numpy and pytest on first use;
`dist`, `version` and `increment` only need a system Python 3.9 or later:
the first of `python3` and `python` that actually runs (on Windows and
Cygwin `python3` is often the Microsoft Store placeholder, which is
skipped). `make dist` builds the zip with Python itself, so no `zip`
command is needed. CI runs the
suite and ruff on Python 3.9 and 3.12.

`make smoke` boots each QGIS found in `/Applications` with its own Python,
offscreen, and checks that the plugin imports, reports through the real
message bar, builds its window, searches, fetches icons through the QGIS
network stack (again on a repeated search), and reads the installed plugins
from disk. Set `SMOKE_DB` to an embeddings database to include the real
search checks.

To try a working copy in QGIS, copy or symlink `SemanticPluginSearch/` into
the profile's `python/plugins/` folder, or install the zip from `make dist`.

## The pipeline

`.github/workflows/BuildEmbeddings.yml` is one job with no QGIS and no
release API. Monday 03:00 UTC builds QGIS 3.44, Tuesday builds QGIS 4.2, and
a manual run builds both. Each run:

1. checks out the `embeddings` branch into `store/`;
2. converts the pinned model from Hugging Face **only when the branch has
   none** (the first run, or after deleting it to change models), so
   Hugging Face is not called otherwise;
3. fetches the catalogue and readmes (`FetchCatalogue.py`). Readmes of
   unchanged plugins come from the branch's `Readmes-<universe>.json.gz`
   cache, so a weekly run only downloads new or updated plugins (a plugin
   that had no readme is retried after 28 days). For those, raw readme
   guesses come first, then one GitHub API call only when every guess
   missed, and a capped package download as the last resort. A manual run
   with *refresh_readmes* fetches everything again;
4. builds each embeddings database (`BuildEmbeddings.py`);
5. stores them (`StoreEmbeddings.py`): content addressed file names, the
   universes not rebuilt carried over, the run refused if a universe has no
   plugins or its count moved more than 10% (`PublishGate.py`), stale files
   pruned, and `index.json` written;
6. force pushes the branch as a single commit, so it never accumulates
   history.

The job stops after 60 minutes. The plugin reads
`https://raw.githubusercontent.com/<repo>/embeddings/index.json`, and because
the data files carry a content hash in their names, the raw host's cache
can never pair a new index with an old file.

## Committing

Every commit bumps the plugin version with its changelog entry, in the same
commit: `make increment INC=rel COMMENT="..."` for fixes, `INC=min` for new
features, `INC=maj` for breaking changes. `make dist` then packages that
version.

## Releasing the plugin

1. `make increment INC=rel COMMENT="What changed"` (or `INC=min`, `INC=maj`,
   or `make version VERSION=x.y.z COMMENT="..."`). This sets the version in
   `metadata.txt` and adds the changelog entry. Without `COMMENT`, the entry
   reads `<version> - TODO describe this release`: replace the TODO with
   what changed.
2. `make test`, then `make dist`. `make dist` runs `tools/PackageCheck.py`
   (repository rules, LICENSE, no binaries, QGIS network stack only, every
   private attribute defined, changelog entry not a TODO) and refuses to
   package on any problem; it needs no venv.
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
