# Semantic Plugin Search for QGIS

**Find the QGIS plugin you need by describing what you want to do.**

There are more than 3,000 QGIS plugins, and the plugin manager only finds
them by keyword: you have to already know the word a plugin's author
used. Semantic Plugin Search lets you express the need instead, in your own
language:

> *classify a drone orthophoto into land cover classes*
> *créer des courbes de niveau à partir d'un MNT*
> *exportere prosjektet til et interaktivt nettkart*

## New in 0.7: search in your language

Earlier versions understood English only. A query in another language mostly
found plugins whose texts happened to be written in that language, not the
plugins that do the job. From 0.7 the plugin uses a multilingual model: you
can describe your need in French, German, Norwegian, Polish, Arabic, Japanese
and many other languages, and it finds the plugins described in English.

| measured on the benchmark | up to 0.4.8 | 0.7 |
|---|---|---|
| a need matches its own translation (21 languages, every pair) | 31% | 87% |
| quality kept by a French, German, Spanish, Portuguese or Italian query, relative to English | 18% | 74% |
| results written in the query's own language rather than matching its meaning | 73% | 7% |
| English, description of the need (nDCG@10) | 0.518 | 0.498 |
| English, keywords (nDCG@10) | 0.558 | 0.585 |

English results stay on a par; the 0.7 figures are still being completed
(about 12% of its English first screens are not yet judged). Icelandic is the
weakest language (65% against English), since the model was not trained on
it. The [roadmap](ROADMAP.md) explains how this will improve.

Installations of 0.4.8 and earlier keep their English model until you update
the plugin.

## Objective

Move plugin search from keywords you must already know to a statement of
what you want to do. It has two levels:

1. **As good as keyword search, from a description of the need.** The
   results need not be better than a well-chosen keyword search. They have
   to be as good when you describe the need in your own words. The search
   is not better, it is better suited: you no longer need to know the
   field's vocabulary or a plugin's name to find it.
2. **Better than keyword search.** The results themselves should beat what
   a keyword search returns.

The project tests and evaluates different techniques against both levels,
on a fixed benchmark, and keeps only what the measurements support.

## Where it stands

Measured on 40 needs, each with the plugins that do it (see
[the evaluation](docs/SearchQualityEvaluation.md)). The queries are written
blind by a separate model, which never saw the plugin catalogue: a short
sentence for this search, and the keywords a keyword search user would type.

- **Level 1 is reached for English.** A short description ranks as well as
  a good keyword search with good keywords; the difference is within noise.
  This search is never empty. The plugin manager's own search finds nothing
  for any of these descriptions.
- **Level 2 is not reached yet.** A keyword ranker still puts more relevant
  plugins on the first screen. Long, detailed descriptions also weaken the
  current model, so short descriptions work best.
- **Level 1 now holds across languages.** With the multilingual model, a
  need in one of the benchmark's 21 languages finds its English counterpart
  95–100% of the time, except Icelandic at 65%. Arabic, Chinese, Greek,
  Japanese and Russian included.

## Techniques

- **In use:** a static text embedding (the plugin and your description
  become vectors, compared by cosine similarity), combined with a lexical
  boost for literal matches in plugin names, tags and descriptions. It runs
  inside QGIS with numpy only, and nothing leaves your computer.
- **Under evaluation:**
  - larger or retrieval-tuned static models;
  - a stronger keyword component, such as BM25, combined with the
    embedding;
  - neural (transformer) models, measured as a quality ceiling.

  The [BenchmarkEmbeddings](.github/workflows/BenchmarkEmbeddings.yml)
  workflow benchmarks each candidate on GitHub, on the same data, so every
  result can be reproduced.

## Roadmap

Two projects are under way to extend the multilingual search (details in
[ROADMAP.md](ROADMAP.md)):

- **Language identification.** A lightweight language identification model,
  [langid-32](https://github.com/SylvainSouche/langid-32), will tell which
  language a query is written in, so the search can add the matching
  vocabulary for that language.
- **A multilingual GIS glossary.** Equivalent GIS terms across languages,
  from sources whose holders allow reuse. It will add the English
  equivalents of a query's GIS terms to the keyword part of the search, and
  fine-tune the model, with extra attention to the languages it handles
  least well today (Icelandic, Greek, Arabic, Nynorsk).

## What it does

- **Search in plain language, in your language.** Results update as you
  type, and typing a plugin's name puts it first.
- **See everything about a plugin at a glance**: icon, description, version,
  compatibility, rating, links and its readme.
- **Know what you already have.** Installed plugins carry a green
  *✓ Installed* badge, or an orange *↑ Update* one when a newer version exists.
- **Install, upgrade, reinstall or uninstall** from the same window. The
  standard QGIS plugin manager does the work, as usual.
- **Private by design.** What you type never leaves your computer.
- **Works offline** after the first launch, and stays up to date on its own:
  the plugin index is rebuilt every week.

## Get started

1. **Requirements:** QGIS 3.44 or later, or QGIS 4.x, and an internet
   connection on first launch (about 30 MB is downloaded once). Nothing else
   to install.
2. **Install:** download `SemanticPluginSearch.<version>.zip`, then in QGIS
   use *Plugins › Manage and Install Plugins… › Install from ZIP*.
3. **Open** *Plugins › Semantic Plugin Search*, or click its toolbar icon,
   and describe what you are looking for.

The [user guide](docs/UserGuide.md) covers search tips, reading the results,
offline use, privacy, settings and troubleshooting.

## Status

The plugin is **experimental**. It has been tested on QGIS 3.44 and QGIS 4.2.
Please report problems and suggestions on the
[issue tracker](https://github.com/SylvainSouche/qgis-semantic-plugin-search/issues).

## How it works

Every week a GitHub Action downloads the official plugin catalogue and every
readme, turns each plugin into a vector with a compact, commercially
licensed text embedding model, and stores the result in this repository's
`embeddings` branch. The plugin
downloads that index and the model once, turns your description into a
vector locally, and ranks plugins by similarity, with a small boost for
plugins whose name or tags contain your words. No AI service is called and
nothing is uploaded.

## For developers

The [developer guide](docs/Developer.md) covers the architecture, the
pipeline, building, testing (`make test` runs without QGIS, and `make smoke`
runs inside a real QGIS) and releasing. The specification is generated
from the project model into [docs/Specification.md](docs/Specification.md).

## License

[MIT](LICENSE), compatible with the GPLv2-or-later requirement for QGIS
plugins. The search model is
[sentence-transformers/static-similarity-mrl-multilingual-v1](https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1)
(Apache-2.0), kept at 256 dimensions. Earlier versions used
[minishlab/potion-base-8M](https://huggingface.co/minishlab/potion-base-8M)
(MIT, distilled from BAAI/bge-base-en-v1.5).
