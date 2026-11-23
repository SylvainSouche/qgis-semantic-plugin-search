# Changelog

Every commit to the plugin bumps its version, so most versions below are
development steps; the headings group them by series. The same entries,
one line each, are in the `changelog` of
[metadata.txt](SemanticPluginSearch/metadata.txt), which the QGIS plugin
manager shows. Plans are in the [roadmap](ROADMAP.md).

## 0.7: Search in your language

The plugin uses a multilingual static model and reads its own data set,
`index-ml.json`, so versions up to 0.4.8 keep their English model and data.
The first release on the QGIS plugin repository since 0.4.8.

- **0.7.3** (2026-11-23): metadata.txt without percent signs, which the plugin repository rejects; make dist and make increment now refuse them
- **0.7.2** (2026-11-23): CHANGELOG.md with every version grouped by series; make increment adds each new entry to it
- **0.7.1** (2026-11-23): Tests run Python 3.9 and 3.12 in the official Python containers
- **0.7.0** (2026-11-23): Search in your own language: multilingual model (21 languages measured, a need matches its translation 87% of the time against 31% before), English results on a par; plugin index stored as int8, about 45% smaller

## 0.6: Multilingual model

Development series, not published: the multilingual model is chosen with the
embedding benchmark, and the tokenizer is brought to parity with the
reference.

- **0.6.4** (2026-11-14): GIS vocabulary rerun with the updated glossary: no gain beyond noise, not shipped; benchmark kept
- **0.6.3** (2026-11-14): GIS vocabulary benchmark rebuilt from the updated gis-glossary (INSPIRE, OpenStreetMap tagging schema, GEMET and CORINE added): 4,881 words
- **0.6.2** (2026-11-12): Benchmark also reruns when the search engine, tokenizer, model loader or converter change
- **0.6.1** (2026-11-12): Tokenizer matches the reference BERT tokenizer exactly: control and format characters removed, text kept decomposed after accent stripping, lowercasing per character
- **0.6.0** (2026-11-12): Multilingual search: the static model becomes static-similarity-mrl-multilingual-v1 (Apache-2.0, 256 dimensions, int8), chosen with the embedding benchmark; the model stays int8 in memory

## 0.5: Search quality evaluation

Development series, not published: the benchmark every later change is
measured on, and the int8 model and databases.

- **0.5.8** (2026-11-12): Benchmark also reruns when queries, judgments or evaluation code change
- **0.5.7** (2026-11-12): Language matrix over the 21 languages the plugin aims to serve, Arabic included
- **0.5.6** (2026-11-12): Language matrix over the gis-glossary project's languages: the 40 needs translated into Norwegian Bokmål and Nynorsk, Icelandic, Danish, Swedish, Polish, Slovenian, Slovak, Greek, Romanian and Bulgarian
- **0.5.5** (2026-11-12): Embedding benchmark: language matrix (alignment of the same need across nine query languages) and reruns named in a commit message
- **0.5.4** (2026-11-12): Benchmark of GIS vocabulary added to the static model, from the gis-glossary project; potion-base-8M's origin corrected to bge-base-en-v1.5
- **0.5.3** (2026-11-12): int8 search model and int8 copies of the plugin vector databases: about half the first download, no measured quality loss, released versions keep working
- **0.5.2** (2026-11-12): README states the objective (describe a need instead of knowing keywords, then beat keyword search), where it stands and the techniques evaluated
- **0.5.1** (2026-11-12): Search evaluation with blind sentence and keyword queries, keyword sessions, and an embedding model benchmark workflow
- **0.5.0** (2026-11-12): Search quality evaluation against keyword baselines and a cross language assessment

## 0.4: Ready for the plugin repository

Released versions. The data they read (`index.json`, potion-base-8M) is
still maintained.

- **0.4.8** (2026-10-30): Author email in the metadata, ready for the plugin repository
- **0.4.7** (2026-10-30): make works on Cygwin and Windows: skips the Microsoft Store python3 placeholder and builds the zip without the zip command
- **0.4.6** (2026-10-30): make rebuilds a .venv whose Python no longer runs (removed or upgraded interpreter) instead of failing
- **0.4.5** (2026-10-30): make dist, version and increment need no venv or numpy and work where Python is called python (Cygwin, Windows); the package checks run standalone
- **0.4.4** (2026-10-30): Install plugins published only as experimental in their experimental version; every error, including the plugin installer's own failures, opens a popup
- **0.4.3** (2026-10-30): Correct plugin installation data refresh
- **0.4.2** (2026-10-30): Correct search result list appearance
- **0.4.1** (2026-10-30): Fix the embeddings workflow and its integration into the plugin
- **0.4.0** (2026-10-30): Fix the window failing to open in 0.3.0 (stale package), fix search never activating after a database update (model check error), icons now return on every search, installed plugins are recognised so Upgrade, Reinstall and Uninstall work, installed and update badges, hybrid ranking that puts exact plugin names first, downloads through the QGIS network settings (proxy, authentication), embeddings served from the repository embeddings branch

## 0.3: Hardening

- **0.3.0** (2026-10-30): Offline first cache, pinned update channel, safer links, bounded background work, hardening

## 0.2: Icons, QGIS 4 and filters

- **0.2.0** (2026-10-29): Plugin icons in the results, QGIS 3 and QGIS 4 installer support, experimental and deprecated filters, live search

## 0.1: First release

- **0.1.0** (2026-10-29): First release: natural language plugin search with local embeddings
