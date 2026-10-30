# Semantic Plugin Search — specification

Generated from `project-model/` · schema_version 2 · 207 objects in model
Sources: 4 CON, 3 NREQ, 39 REQ, 8 UC
Generated 2026-10-30. Regenerate rather than edit — hand edits are lost and drift silently.

## Constraints

### Only models whose license allows commercial use may have vectors or weights distributed through the project; non commercial models are allowed only for testing during development

`CON-con-commercial-models` · status **recorded** · id `0f87-6ae3-6956-b93e`

### The QGIS plugin repository requires mandatory metadata with working homepage, repository and tracker links, an author email, a GPLv2 compatible LICENSE inside the package, a changelog for updates, qgisMaximumVersion of at least 4.0 for QGIS 4, no binaries or generated or hidden files, a plugin name not repeating the word plugin, and network requests through the QGIS network manager so proxy settings apply; uploads pass a bandit, flake8 and detect-secrets scan

`CON-con-qgis-repository-rules` · status **recorded** · id `4be9-6ae3-f4ac-6896`

### The embedding engine must be small and fast and must run inside the plugin on any QGIS compatible computer, including model download at launch and local caching

`CON-con-light-engine` · status **recorded** · id `0f87-6ae3-6956-5e6b`

### The plugin must run inside the QGIS bundled runtimes: Python 3.9 or later plus PyQt5 on QGIS 3.x and PyQt6 on QGIS 4.x, using only libraries QGIS already ships

`CON-con-qgis-runtime` · status **recorded** · id `0f87-6ae3-6956-aab8`

## Negative requirements

### No vector database or model file distributed through the project releases or plugin downloads may derive from a model that does not allow commercial use; non commercial models are confined to development test fixtures that are never published

`NREQ-nreq-no-noncommercial-vectors` · status **confirmed** · id `0f87-6ae3-6996-571d`

### The raw user query text never leaves the user machine

`NREQ-nreq-query-stays-local` · status **confirmed** · id `0f87-6ae3-6996-386d`

Refines: `req-natural-language-search`

### The search window never performs installation operations itself; install, upgrade, reinstall and uninstall are always delegated to the standard plugin manager

`NREQ-nreq-no-own-install` · status **confirmed** · id `0f87-6ae3-6996-c732`

Refines: `req-action-integration`

## Requirements

### A Makefile at the repository root provides help, test, smoke, fetch, embed, dist, version, increment, clean and clean-all; embed fetches the catalogue and readmes first when missing, fetch and embed cover the configured QGIS version universes, version VERSION=x.y.z sets and increment inc=maj|min|rel bumps the plugin version with a changelog entry to fill in, and clean keeps the model tooling in build/ddd

`REQ-req-makefile-targets-v2` · status **confirmed** · id `4be9-6ae4-41db-88b2`

Supersedes 0f87-6ae3-7ce1-fb2e (A Makefile at the repository root provides clean, clean-all, package, help, fetch, embed and test; embed fetches the catalogue and readmes first when they are missing, and fetch and embed cover the configured QGIS version universes).

Carries forward what remained valid and states what changed.

### A new embeddings database is activated only when the cached model's id matches the database's model id, reloading the model file once when the loaded model differs; with no model yet the search waits without error, and a mismatch pauses search with a message

`REQ-req-model-pairing` · status **confirmed** · id `4be9-6ae4-3eac-c78b`

Refines: `req-auto-updated-assets`

### A newer database replaces the local copy atomically and only after integrity checks pass, and a failed update leaves the previous cache fully usable

`REQ-req-atomic-cache-update` · status **confirmed** · id `0f87-6ae3-6985-9c48`

Refines: `req-auto-updated-assets`

### A run fetches only the readmes of plugins that are new or whose version or repository changed, plus cached misses older than 28 days, reusing the others from a Readmes-<universe>.json.gz cache on the embeddings branch that holds exactly the current catalogue; a manual run can force a full refresh

`REQ-req-readme-cache` · status **confirmed** · id `4be9-6ae4-3a55-8652`

Refines: `req-fetch-budget`

### Beneath the search field a line reads Type a query to search plugins while the query is empty, N plugins found matching your query after a search, No plugin found matching your query when nothing matched, and Preparing the search while the index is not ready

`REQ-req-search-summary` · status **confirmed** · id `4be9-6ae4-4051-90cf`

Refines: `req-window-polish`

### Each result row presents the plugin icon, a bold sans serif plugin name line and a smaller serif description line left aligned two pixels from the icon, and the relevance percentage, capped at 100, right aligned on the name line; installed plugins carry a green check mark Installed pill beside the name, plugins with a newer version an orange Update pill, and experimental or deprecated plugins a muted word after it

`REQ-req-result-rows-v3` · status **confirmed** · id `4be9-6ae4-4682-9629`

Supersedes 4be9-6ae3-f123-64dd (Each result row presents the plugin icon, a bold sans serif plugin name line and a smaller serif description line left aligned two pixels from the icon, and on the right a column with the relevance percentage, capped at 100, aligned with the name line and, for installed plugins, a muted installed or update badge beneath it).

Carries forward what remained valid and states what changed.

Refines: `req-window-polish`

### Every download the plugin makes, release index, model, databases, readmes and icons, goes through the QGIS network stack so the user's proxy, SSL and authentication settings apply, bypassing the QGIS network cache, with the plugin code importing no other network library

`REQ-req-qgis-network-stack` · status **confirmed** · id `4be9-6ae3-f4ad-b6ea`

Refines: `req-auto-updated-assets`

### GitHub Actions periodically rebuild per QGIS version embedding databases from the full plugin catalogue and readmes and publish them with an update index

`REQ-req-pipeline` · status **confirmed** · id `0f87-6ae3-6970-949f`

### Identifiers use CamelCase: UpperCamelCase for classes and modules and Qt style camelCase for methods, matching the surrounding PyQt ecosystem

`REQ-req-camelcase-naming` · status **confirmed** · id `0f87-6ae3-6986-14e6`

Refines: `req-architecture-quality`

### Install, upgrade, reinstall and uninstall actions are available in the search window and delegate to the standard plugin manager

`REQ-req-action-integration` · status **confirmed** · id `0f87-6ae3-6970-313d`

### No plugin's metadata can resize the panes: the result list keeps at least 280 px, neither pane collapses, every metadata field wraps and is shown as plain text, row descriptions are elided, experimental and deprecated show beside the name, and catalogue text is shown with its HTML entities decoded

`REQ-req-robust-layout` · status **confirmed** · id `4be9-6ae4-4521-3222`

Refines: `req-two-pane-layout`

### On first use the plugin downloads the embedding model and the database for its QGIS version and caches them without user configuration

`REQ-req-first-run-bootstrap` · status **confirmed** · id `0f87-6ae3-6985-a030`

Refines: `req-auto-updated-assets`

### One plugin codebase runs unchanged on QGIS 3.44 and on QGIS 4.0 and 4.2

`REQ-req-portability-v2` · status **confirmed** · id `0f87-6ae3-746d-1a0c`

Supersedes 0f87-6ae3-6970-90c5 (One plugin codebase runs unchanged on QGIS 3.34 and on QGIS 4.0 and 4.2).

Carries forward what remained valid and states what changed.

### One user event produces at most one background job and one batched GUI callback per concern, icons and readmes are deduplicated and staleness tokened, the model never parses on the GUI thread, and a separator keystroke triggers the search while mid word typing debounces

`REQ-req-event-discipline` · status **confirmed** · id `0f87-6ae3-e355-74a5`

Refines: `req-architecture-quality`, `req-window-polish`

### Qt imports go through qgis.PyQt indirection and only APIs available in both PyQt5 and PyQt6 are used

`REQ-req-pyqt5-pyqt6` · status **confirmed** · id `0f87-6ae3-6986-bc9f`

Refines: `req-portability-v2`

### Results are ordered by descending hybrid score, the cosine similarity between the query and plugin embeddings plus a bounded lexical boost for an exact plugin name match and for query words found in the plugin name, tags and description; a query with no known token can still match by name

`REQ-req-hybrid-ranking` · status **confirmed** · id `4be9-6ae3-f123-5b3c`

Supersedes 0f87-6ae3-6985-5a6f (Results are ordered by descending cosine similarity between the query embedding and the stored plugin embeddings).

Carries forward what remained valid and states what changed.

Refines: `req-natural-language-search`

### The codebase follows strict MVC with isolated roles, CamelCase naming, and a QGIS independent test harness

`REQ-req-architecture-quality` · status **confirmed** · id `0f87-6ae3-6970-181f`

### The domain and data layers import neither qgis nor Qt, the presentation contains no business logic, controllers orchestrate through view and service interfaces, and QGIS specific services are isolated behind adapters

`REQ-req-mvc-isolation` · status **confirmed** · id `0f87-6ae3-6986-f061`

Refines: `req-architecture-quality`

### The embeddings, the model and the index file are stored on a dedicated embeddings branch of the project repository, rewritten by each CI run as a single commit with content addressed data file names, and the plugin fetches the index from that branch through raw.githubusercontent

`REQ-req-embeddings-branch` · status **confirmed** · id `4be9-6ae3-f849-7641`

Supersedes 0f87-6ae3-6997-428c (Publish an index file with per universe database checksums and build dates and serve binaries through GitHub latest release download URLs so the plugin can decide whether its cache is stale).

Carries forward what remained valid and states what changed.

Refines: `req-pipeline-publish`

### The pipeline downloads the official plugin catalogue for each QGIS version and each plugin readme from its repository or package archive, adapting the existing fetcher

`REQ-req-pipeline-fetch` · status **confirmed** · id `0f87-6ae3-6986-4446`

Refines: `req-pipeline`

### The pipeline embeds text derived from each plugin name, description, about, tags and a size capped readme excerpt, using the same model the plugin uses for queries

`REQ-req-pipeline-embed` · status **confirmed** · id `0f87-6ae3-6986-9d64`

Refines: `req-pipeline`

### The pipeline resolves each readme from raw repository guesses before at most one GitHub API call, falls back to a plugin package capped at 25 MB, bounds every download by size and wall clock time, flushes its progress, stops the job after 60 minutes, and downloads the model from Hugging Face only when none is stored

`REQ-req-fetch-budget` · status **confirmed** · id `4be9-6ae3-f84a-d578`

Refines: `req-pipeline-fetch`

### The pipeline stores embeddings and a metadata snapshot per QGIS version into the distributable database and publishes databases, model and an index file for update checks

`REQ-req-pipeline-publish` · status **confirmed** · id `0f87-6ae3-6986-d290`

Refines: `req-pipeline`

### The plugin computes the query embedding locally in process from the raw user input using the cached model

`REQ-req-query-embedding-local` · status **confirmed** · id `0f87-6ae3-6985-7c77`

Refines: `req-natural-language-search`

### The plugin downloads only the database built for its QGIS version universe, QGIS 3 or QGIS 4

`REQ-req-db-version-match` · status **confirmed** · id `0f87-6ae3-6985-6264`

Refines: `req-auto-updated-assets`

### The plugin package carries complete repository metadata, mandatory fields with https links to the code repository and its tracker, a changelog opening with the current version, qgisMaximumVersion 4.99, an about text stating the download and dependency requirements, and a LICENSE file identical to the repository one

`REQ-req-repository-metadata` · status **confirmed** · id `4be9-6ae3-f4ad-668c`

Refines: `req-makefile-targets-v2`

### The plugin reads the installed plugins from the plugin folders on disk, matching a result by installer key, then case insensitively, then by declared name, so the action buttons follow the real installed state, refresh after every action, and stay disabled when the state cannot be read

`REQ-req-installed-state` · status **confirmed** · id `4be9-6ae3-f12c-0110`

Refines: `req-manager-buttons`

### The plugin ships without binary dependencies beyond the libraries QGIS already bundles, such as numpy and the standard library

`REQ-req-bundled-deps-only` · status **confirmed** · id `0f87-6ae3-6986-51e1`

Refines: `req-portability-v2`

### The pytest suite exercises search ranking, embedding computation, database update, details orchestration, action delegation and pipeline builds with fakes and runs without QGIS installed

`REQ-req-tests-without-qgis` · status **confirmed** · id `0f87-6ae3-6986-4c12`

Refines: `req-architecture-quality`

### The result list sits on the left and the right panel shows metadata of the selected plugin, defaulting to the first result when nothing is selected

`REQ-req-two-pane-layout` · status **confirmed** · id `0f87-6ae3-6985-53e9`

Refines: `req-result-presentation`

### The results exclude experimental and deprecated plugins by default; two toggles in the window include each category again and the choice is persisted per profile

`REQ-req-visibility-filters` · status **confirmed** · id `0f87-6ae3-a1e6-cf4c`

Refines: `req-result-presentation`

### The right panel has two tabs, Metadata as the default and Readme, and the readme fetch starts in the background when a plugin is selected and never blocks the list

`REQ-req-two-tabs` · status **confirmed** · id `0f87-6ae3-6985-9f7c`

Refines: `req-result-presentation`

### The search window presents ranked results on the left and details of the selected plugin on the right

`REQ-req-result-presentation` · status **confirmed** · id `0f87-6ae3-6970-4b22`

### The search works from locally cached assets, an embedding model and an embeddings database, that the plugin keeps up to date automatically from the project GitHub

`REQ-req-auto-updated-assets` · status **confirmed** · id `0f87-6ae3-6970-f0a1`

### The window exposes the same action buttons as the standard plugin manager, Install, Upgrade, Reinstall and Uninstall, enabled according to the plugin state

`REQ-req-manager-buttons` · status **confirmed** · id `0f87-6ae3-6985-0cec`

Refines: `req-action-integration`

### The window offers live search while typing with a short debounce, remembers its geometry and splitter layout per profile, and shows result rows with name, similarity and a description excerpt

`REQ-req-window-polish` · status **confirmed** · id `0f87-6ae3-a1e6-0cd7`

Refines: `req-result-presentation`

### Users can find QGIS plugins with natural language queries instead of keyword matching

`REQ-req-natural-language-search` · status **confirmed** · id `0f87-6ae3-6970-f113`

### Version control ignores the downloaded plugins metadata and readmes, the embeddings databases and the converted model

`REQ-req-gitignore-generated` · status **confirmed** · id `0f87-6ae3-7f88-fc1b`

### make dist runs the full test suite first and refuses to package when it fails, including while the current version's changelog entry is still a TODO, and the suite statically requires every private attribute a plugin class reads to be defined

`REQ-req-package-guard-v2` · status **confirmed** · id `4be9-6ae4-41dc-de55`

Supersedes 4be9-6ae3-f12c-682d (make package runs the full test suite first and refuses to package when it fails, and the suite statically requires every private attribute a plugin class reads to be defined).

Carries forward what remained valid and states what changed.

Refines: `req-makefile-targets-v2`

## Use cases

### A QGIS user opens the semantic plugin search, types a natural language need such as finding tools to classify a drone orthophoto into land cover classes, and sees a ranked list of matching plugins within seconds

`UC-uc-search` · status **confirmed** · id `0f87-6ae3-695e-9458`

### A QGIS user scans the results, sees which plugins are already installed or have an update, and upgrades, reinstalls or uninstalls one from the window, after which the badge and buttons reflect the new state

`UC-uc-see-installed` · status **confirmed** · id `4be9-6ae3-f4ad-e49b`

### A QGIS user selects a result in the list and reads its metadata on the right panel, which shows the first result by default, then opens the Readme tab whose content loads in the background once the selection changes

`UC-uc-inspect` · status **confirmed** · id `0f87-6ae3-695e-7151`

### A QGIS user triggers Install, Upgrade, Reinstall or Uninstall from the search window and the operation is carried out by the standard plugin manager machinery

`UC-uc-act` · status **confirmed** · id `0f87-6ae3-695e-d7d1`

### A QGIS user who remembers a plugin name, or part of it, types it in the search box and finds that plugin at the top of the list

`UC-uc-find-by-name` · status **confirmed** · id `4be9-6ae3-f4ad-99af`

### A developer runs the full functional test suite on a machine without QGIS installed, covering search ranking, embedding computation, database update, details display, action delegation and pipeline builds

`UC-uc-dev-test` · status **confirmed** · id `0f87-6ae3-695f-8c38`

### A project maintainer relies on periodic GitHub Actions runs to download the plugin catalogue and readmes, compute embeddings for the QGIS 3 and QGIS 4 plugin universes, and publish the databases together with an index for update checks

`UC-uc-build` · status **confirmed** · id `0f87-6ae3-695f-cd51`

### On opening the search window the plugin checks GitHub for an embeddings database newer than its cached one for the running QGIS version, downloads and stores it when appropriate, and falls back to the cache when offline or when no newer build exists

`UC-uc-refresh` · status **confirmed** · id `0f87-6ae3-695f-647a`

