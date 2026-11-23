# Roadmap

Semantic Plugin Search aims at two levels (see the [README](README.md)):
first, finding a plugin from a description of the need as well as a good
keyword search would; then doing better than keyword search. Since 0.7.0 the
first level also holds across languages. The work below extends it to more
languages and more vocabulary.

Each step is measured on the project's fixed benchmark before it ships
([evaluation](docs/SearchQualityEvaluation.md)). A step that does not improve
the measurements is not shipped.

## Released

**0.7.0: search in your language.** The plugin uses a multilingual static
model
([static-similarity-mrl-multilingual-v1](https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1)).
Across the 21 languages of the benchmark, a need matches its own translation
87% of the time, against 31% with the previous English model, and English
results stay on a par. The weakest language is Icelandic, which the model was
not trained on.

## In progress

### Language identification

A lightweight language identification model is being built in a separate
project, [langid-32](https://github.com/SylvainSouche/langid-32): 34
languages, trained on a balanced corpus whose sources are all checked for
reuse rights.

In the plugin, it will tell which language a query is written in, so the
search can add the right vocabulary for that language (next section). It has
to work on very short input, a few words or a single keyword, and to say when
it is unsure, in which case the search behaves as it does today. The model
must run inside QGIS with numpy only, so the plugin will use its compact
character n-gram variant.

In the pipeline, it will also label the language of each plugin's
description and readme, giving a reliable picture of which languages the
catalogue is written in.

### A GIS glossary for multilingual search

A multilingual GIS glossary is being assembled in a separate project
(gis-glossary): equivalent terms across languages, from standards bodies,
national terminology services, the QGIS translations, INSPIRE, OpenStreetMap
and others. Every term keeps its source, and only sources whose holders allow
reuse are used in what the plugin ships. Some holders have not answered yet;
their terms join as permission arrives.

The glossary will serve in two ways:

1. **Cross-language keywords.** The keyword part of the search only matches
   words in the query's own language. The glossary will add the English
   equivalents of the GIS terms in a query (for example *høydekurver* →
   *contour lines*), guided by the language identification. The user's own
   words are always kept; equivalents only add to them.
2. **Fine-tuning the model.** The search model will be fine-tuned on glossary
   term pairs and on general translation pairs, with extra weight on the
   languages it handles least well today: Icelandic, Greek, Arabic and
   Nynorsk. Local experiments show that glossary fine-tuning improves how
   well a static model aligns languages (from 75% to 87% on the benchmark's
   language matrix).

## Next

- **Cleaner plugin texts.** Skip readme sections that say nothing about what
  a plugin does (installation, licence, changelog, credits) and always
  include the readme's section headings, so more of what a plugin does fits
  in what is indexed.
- **Level 2 in English.** Combine the embedding with a stronger keyword
  ranker (BM25), which the benchmark shows to help static models.

## Not planned

Neural (transformer) models rank better, but need a runtime QGIS does not
ship and are much larger. The benchmark keeps measuring them as a quality
ceiling.
