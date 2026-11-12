# Search quality evaluation (0.5 development)

Two questions, asked on 2026-11-12 at the start of the 0.5 line:

1. Is the shipped search really better than pure keyword search, with each
   used the way it is meant to be used: a sentence for the semantic search,
   keywords added one at a time for keyword search?
2. How well does it work across languages: a non English query, or a plugin
   documented in another language?

The numbers below come from `evaluation/Results.md`, regenerated with
`make eval`. This page interprets them.

## Short answers

**How the comparison is set up.** Each of 40 needs comes with the plugins that
do it (the judgments). Each need is then asked in two forms:

- a sentence, as typed into a search box that understands plain language;
- the keyword list a keyword search user types, in order.

Both forms were written by a separate model, Claude Haiku at medium effort. It
was given only the task and the prompt in `evaluation/QueryPrompt.txt`: no
plugin names, no catalogue, no other task.

Both forms run on every backend, because a keyword list can be typed into the
semantic box too. Keyword search is also replayed as it is really used: type
one keyword, look at the first screen, and add the next keyword only if it
shows nothing that does the task.

Every plugin any of these runs shows on its first screen is judged. So the
precision of what each run returns is known, not just how many results it
returns. The evaluation author's own wording is kept as `author` rows for
comparison.

**Against keyword search.** On ranking, a sentence user on the shipped search
and a keyword user on a good keyword ranker are now within noise of each
other. On precision, the keyword user still sees clearly more relevant plugins
on the first screen.

| QGIS 3, 40 needs | nDCG@10 | share of the first screen relevant | a plugin that does the task on it |
|---|---|---|---|
| BM25, keyword list | **0.565** | **0.645** | **97.5 %** |
| shipped hybrid, sentence | 0.518 | 0.540 | 92.5 % |
| shipped hybrid, keyword list | 0.558 | 0.593 | 97.5 % |
| shipped hybrid, first keyword only | 0.548 | 0.545 | 97.5 % |
| "all keywords" filter, keyword list | 0.165 | 0.372 | 52.5 % (no result for 37.5 % of needs) |
| plugin manager phrase filter, keyword list | 0 | 0 | 0 % (no result for every need) |

- **BM25 with keywords against the hybrid with a sentence, QGIS 3.**
  - nDCG@10 −0.047 (95 % interval −0.132 to +0.035), within noise;
  - precision@10 −0.105 (−0.185 to −0.028), significant;
  - found@10 −5 points, within noise.
- **The same comparison on QGIS 4.**
  - nDCG@10 −0.021, within noise;
  - precision@10 −0.080, significant;
  - found@10 −12.5 points, significant.
- **The shipped search typed as keywords** matches BM25 with the same keywords:
  nDCG@10 −0.007, precision@10 −0.053, both within noise.
- **Sentences cost BM25 precision** (−0.102 precision@10, significant). The
  first version of this evaluation fed BM25 sentences, which made the hybrid
  look ahead.
- **Adaptive keyword sessions** (QGIS 3):
  - BM25 and the hybrid both reach a plugin that does the task on every
    need, in 1.0–1.1 keywords on average.
  - The "all keywords" filter fails on 7.5 % of needs and the plugin
    manager's filter on 20 %. They empty the list on 12.5 % and 20 % of
    sessions.
  - The share of the final screen that is relevant: BM25 0.590, hybrid
    0.552, filters about 0.55.

**Sentence length matters for the shipped search.** The same model was asked
twice:

| sentence prompt | mean words | hybrid nDCG@10 | found@10 |
|---|---|---|---|
| no length limit | 13.2 | 0.485 | 80 % |
| "fewer than 10 words" (current) | 7.8 | 0.518 | 92.5 % |
| author's sentences | 7.6 | 0.526 | 92.5 % |

- The static embedding averages every word. Extra detail, such as "…snapping
  each point to the nearest road segment", dilutes the query.
- Filler words were not the cause of the drop: removing "QGIS" and "plugin"
  from the long sentences gained only +0.003.
- BM25 barely notices length: 0.481 to 0.495.
- The search box should invite short descriptions.

**What the shipped search does better.**

- It accepts a plain sentence, where the plugin manager finds nothing.
- It is never empty.
- Its first result is right slightly more often with a sentence: MRR 0.871
  against 0.845 for BM25 on the same sentences.
- It helps when the user lacks the field's own word.

**Was the author biased?** No longer measurably.

- With short sentences, Haiku's and the author's sentences score the same on
  the hybrid: −0.008, within noise.
- Haiku's keyword lists also do as well as the author's on BM25: −0.030
  nDCG@10, within noise.

`asm-static-quality` ("clearly better than keyword matching") holds against
filters and the plugin manager. It does **not** hold against keyword ranking
used the way keyword search is used.

**Across languages.** Search effectively works in English only.

- Asked in French, German, Spanish, Portuguese or Italian, the same 40 needs
  keep 13–26 % of their English nDCG@10. Even counting every unjudged result
  as relevant, they stay below 0.25, against 0.53 in English.
- Russian and Japanese queries get almost nothing: 0.002 and 0.021. Chinese
  keeps 29 %.
- The failure has a clear mechanism: **the model matches the query's
  language, not its meaning.** For a European-language query, 65–79 % of the
  top ten are plugins written in that language, whatever their topic, although
  those plugins are only 1–4 % of the catalogue. Asked in French for contour
  lines, the top results are a French watershed tool and French data portals.
- BM25 fails the same way, so this is not a regression of the embeddings.
  Neither approach bridges languages.

**Non English plugins.** About 18 % of the QGIS 3 catalogue (≈ 710 plugins) is
documented mainly in another language: Portuguese, Japanese and Chinese,
Spanish, French, German, Italian, Russian and Korean.

- For regional needs, such as cadastres, national data portals and
  registries, asking in the region's language works well (hybrid nDCG@10
  0.601).
- Asking the same need in English works worse with the hybrid ranking (0.399)
  than with BM25 (0.547). English wording only reaches those plugins through
  literal proper nouns (IBGE, ALKIS, SIGEF, Tianditu), which BM25 weighs more
  heavily.

## Method

**Snapshot.** Everything runs on commit `97fc1c9` of the published
`embeddings` branch. That commit holds the shipped model, both universe
databases and the readme cache they were built from. Pinning it keeps results
comparable across weekly rebuilds. The semantic and keyword systems index
exactly the same text, the one `pipeline/TextPreparation.py` embeds.

**Systems.** All use the default visibility, with experimental and deprecated
plugins hidden.

| system | what it is |
|---|---|
| manager | approximation of the plugin manager search box: the whole query as a case insensitive substring of name, description, author or tags, sorted by name |
| andfilter | the boolean "all keywords" search box: every keyword must start a word of the name, description, about, tags or author, sorted by name. A sentence typed into it keeps its content words |
| bm25 | Okapi BM25 over the embedded text (name, description, about, tags, readme excerpt) |
| bm25stem | the same with a light English suffix stripper |
| lexical | the shipped lexical boost alone (`Domain/LexicalBoost.py`) |
| semantic | the shipped static embedding cosine alone |
| hybrid | the shipped ranking (`Domain/SearchEngine.py`) |
| fusion | not shipped: reciprocal rank fusion of semantic and BM25, as a comparison |

**Needs and queries** (`evaluation/Queries.json`).

- 40 task needs. `en` states the task in a few words.
- `generated` holds a sentence and a keyword list written by Claude Haiku
  (medium effort). The prompt asks for a short, direct sentence of fewer than
  10 words. A first version had no length limit, and its results are kept in
  the table above. There is one independent call per task. The call contains
  only the prompt in `evaluation/QueryPrompt.txt` with that task inserted: no
  plugin names, no catalogue, no other task. The keyword list is ordered: the
  first keyword is tried alone, and each next one is added to the box when the
  results are not good enough.
- `authorKeywords` and `en` are the evaluation author's own wording, kept for
  comparison.
- Every task's `en` carries hand translations into French, German, Spanish,
  Portuguese, Italian, Russian, Chinese and Japanese. The cross-language part
  uses those translations.
- 16 region-specific "native" needs, each in its own language and in English.

**Query forms and sessions.**

- *One shot*: the sentence, the whole keyword list, or its first keyword,
  typed at once.
- *Keyword session*: type the first keyword and read the first screen of ten.
  Stop if it shows a plugin that does the task (grade 2); otherwise add the
  next keyword. A keyword that empties the list is taken back out. The session
  is measured on the screen it stops on.

**Judgments** (`evaluation/Judgments.json`) are graded per need: 2 means the
plugin does the task, 1 means it does so partly, for one region or data source
only, or as a side feature. Both query forms of a need are judged against the
same expected plugins.

- Candidates were pooled from the top results of every system, language and
  query form, listed alphabetically without saying which system found them.
- A pattern search over the whole catalogue found plugins no system had
  retrieved. It recovered real misses: qgis2web, Lizmap and QGIS Cloud for the
  web map query, and ORS Tools for routing and isochrones.
- A second round judged the 1,058 plugins first shown by the author's keyword
  forms; 90 turned out relevant.
- Later rounds judged the plugins first shown by Haiku's queries: 632 from
  the first prompt (26 relevant) and 267 from the short-sentence prompt
  (6 relevant).
- Every English run, sentence or keyword, one shot or session step, has 100 %
  of its first screen judged. So `precision@10` is exact, within the judge's
  reliability.
- Cross-language runs have 50–66 % judged, so their results are a range: the
  judged value, and an optimistic bound where every unjudged result counts as
  relevant.

**Metrics.**

- nDCG@10 is graded and rewards putting the best plugins first.
- `found@10` is whether a plugin that does the task is on the first screen.
- `precision@10` is the share of the first screen that is relevant (or of the
  whole list when it is shorter). A short list of wrong plugins scores 0; it is
  not credited for being short.
- Recall@20, MRR and Success@5 are also reported.
- Comparisons use a paired bootstrap over needs (10,000 resamples) and give a
  95 % interval.

**Limitations to keep in mind.**

- One judge, Claude, reading names, descriptions, about texts and tags.
  `Judgments.json` is plain JSON so it can be reviewed and corrected, and
  `make eval` recomputes everything.
- The main queries come from one model, Haiku, at one effort level, and its
  keywords and sentences are one plausible user among many. Queries collected
  from real users would be the next step. The task statements (`en`) given to
  Haiku were written by the author.
- The session model is simple: one fixed keyword order, no synonym swapped in
  after a miss, and a stop at the first plugin that does the task.
- 40 needs detect differences of about ±0.05 nDCG@10. Smaller differences are
  noise at this size.
- The manager baseline reproduces the plugin manager's phrase filter from
  memory of its behaviour, not from its source.
- Translations are by Claude. Plugin languages are detected with a coarse
  stopword heuristic.

## Where each approach wins (QGIS 3, nDCG@10)

These tables use the author's short sentences (`en`) on both systems. The
hybrid ranking clearly beats BM25 when the user's words differ from the
plugin's:

| query | hybrid | bm25 |
|---|---|---|
| simulate river flooding and inundation depth | 0.630 | 0.273 |
| process a lidar point cloud into a digital terrain model | 0.570 | 0.258 |
| compute NDVI from Sentinel-2 bands | 0.575 | 0.357 |
| analyse public transport timetables from GTFS | 0.779 | 0.396 |
| export the attribute table to an Excel spreadsheet | 0.600 | 0.253 |
| manage and edit the metadata of my layers | 0.420 | 0.157 |

BM25 wins when one distinctive word carries the need and the embedding
average dilutes it:

| query | hybrid | bm25 |
|---|---|---|
| animate a layer over time with a time slider | 0.325 | 0.734 |
| match GPS points to the roads they were recorded on | 0.113 | 0.322 |
| check topology errors in a polygon layer | 0.572 | 0.752 |
| split a polygon into parts of equal area | 0.718 | 0.905 |
| estimate the solar potential of rooftops | 0.375 | 0.544 |

Three queries are hard for every system:

- "interpolate temperature measurements": 0.06 or less everywhere. Plugins
  about thermal imagery outrank the interpolation tools.
- "classify a drone orthophoto": about 0.18.
- "draw an elevation profile": 0.26 or less.

Typing keywords into the shipped search removes the dilution in some cases
and adds it in others. With Haiku's keywords:

- "map matching GPS road network" scores 0.527, against 0.032 for its
  sentence;
- "time slider animation temporal" scores 0.859, against 0.114;
- "topology polygon validation" scores 0.260, against 0.572;
- "coordinates clipboard click" scores 0.317, against 0.611.

The per-need table in `Results.md` has every case.

The fusion experiment, not shipped, matches the hybrid on sentences: 0.525
against 0.518. With Haiku's keywords it reaches nDCG@10 0.568 and
precision@10 0.633, close to BM25 alone.

## Cross language detail (QGIS 3)

| query language | hybrid nDCG@10 | share of English | top ten in the query language | words unknown to the vocabulary | WordPiece pieces per word |
|---|---|---|---|---|---|
| en | 0.527 | 100 % | 98 % | 0 % | 1.19 |
| fr | 0.136–0.245 | 26 % | 79 % | 0 % | 1.68 |
| es | 0.102–0.211 | 19 % | 79 % | 0 % | 1.90 |
| pt | 0.098–0.215 | 19 % | 68 % | 0 % | 1.91 |
| de | 0.074–0.183 | 14 % | 74 % | 0 % | 2.62 |
| it | 0.070–0.164 | 13 % | 65 % | 0 % | 2.02 |
| zh | 0.151–0.245 | 29 % | 57 % | 72 % | 1.04 |
| ja | 0.021–0.158 | 4 % | 96 % | 47 % | 2.22 |
| ru | 0.002–0.134 | 0 % | 100 % | 0 % | 5.94 |

The vocabulary is the English uncased BERT WordPiece (29,528 tokens), and it
explains the three regimes:

- **Latin script European languages** are never unknown but are cut into
  about 2–2.6 fragments per word. Those fragments carry the "French-ness" of
  the text far more than its topic.
- **Russian** falls apart into single characters (5.9 pieces per word). That
  is a pure script signal, so it only ever matches Russian plugins.
- **Chinese and Japanese** lose half or more of their characters to unknown
  tokens. Chinese does a little better because the surviving characters are
  meaningful one by one.

## What this means for 0.5

These are options to decide, not decisions.

1. **Correct the claim.** The README says plugins are ranked "by how well it
   matches", and the assumption says "clearly better than keyword matching".
   An honest claim would be: "describe what you need in your own words;
   far better than the plugin manager's search, and as good as keyword
   search when you already know the right keywords". Settling
   `asm-static-quality` is a user decision.
2. **Keyword side.** With keyword lists, BM25 beats the shipped hybrid on
   precision (significant on QGIS 4), and the shipped hybrid gains nothing on
   BM25. Short keyword queries are common, so a BM25-based lexical component
   deserves a measured trial: normalised into the hybrid score in place of the
   current fixed boosts, or applied only to short queries. Rank fusion ties on
   sentences and is the best system on keyword lists. The target is to keep
   the sentence results and reach BM25's keyword results.
3. **Multilingual** (`cand-multilingual-model`). The problem is the model, not
   the ranking code. Any fix has to bring a cross lingual vocabulary within the
   constraints `con-light-engine` and `con-commercial-models`, for example a
   multilingual static model distilled from a commercially licensed
   multilingual sentence model, pruned to a reasonable download size. The
   other route is translating plugin texts on the GitHub side. The cross
   language part of this evaluation is the yardstick for either.
4. **Keep the harness.** `cand-golden-query-eval` asked for exactly this. It
   now exists as `make eval`; running it in the weekly workflow is still open.

## Benchmarking other embedding models

`evaluation/Candidates.json` lists alternative models, and the
**BenchmarkEmbeddings** GitHub workflow runs each one on the evaluation
above. GitHub's runners do the downloads and the CPU work, so nothing runs on
a developer machine. Every run uses the same pinned snapshot, needs, queries
and judgments.

| class | candidates | why |
|---|---|---|
| static, English | potion-base-8M (shipped), potion-base-32M, potion-retrieval-32M, static-retrieval-mrl-en-v1 | same engine as today: a larger table or a retrieval-tuned one |
| static, multilingual | potion-multilingual-128M, static-similarity-mrl-multilingual-v1 | the cross-language failure; still numpy only, but a larger download and possibly another tokenizer |
| transformer (ceiling) | all-MiniLM-L6-v2, paraphrase-multilingual-MiniLM-L12-v2, multilingual-e5-small, bge-small-en-v1.5 | what a neural model would gain; not shippable under `con-light-engine` |
| static, GIS vocabulary | distill-bge-base (control), distill-bge-base-gis, potion-base-8M-gis | GIS words as whole tokens instead of pieces (con + ##tour, lid + ##ar); see below |
| transformer (teacher) | bge-base-en-v1.5 | the model potion-base-8M was distilled from |

How a candidate is measured:

- Its model embeds exactly the plugin text the shipped database was built
  from.
- The semantic and hybrid systems use its vectors. The hybrid adds the
  shipped lexical boost unchanged.
- The keyword baselines are the same for every candidate.
- The `shipped` candidate goes through the same generic path and reproduces
  `make eval` exactly. `potion-base-8M` loads the same model through
  model2vec, which checks the loader.

Reading the results:

- Each job uploads `<candidate>.json` and `<candidate>.unjudged.json`, the
  plugins that model shows on a first screen and nobody has judged yet.
- The report job merges them into `BenchmarkReport.md`, also shown on the
  run's summary page.
- A value marked * still has unjudged plugins: it is the judged value, with
  the optimistic bound in brackets.
- To make a promising model's numbers exact, judge its `unjudged.json`
  pairs into `Judgments.json` and run the workflow again. The shipped
  model's own English runs stay fully judged.

GIS vocabulary. The shipped model splits many GIS words into generic
pieces: *contour* becomes con + tour, *lidar* lid + ar, *hillshade*
hills + had + e. Even *qgis* and *plugin* are split.
`evaluation/GisVocabulary.tsv` lists 2,466 such words, of which 1,477
appear in plugin texts. They are taken from the English terms of the
gis-glossary project (`evaluation/BuildGisVocabulary.py`; sources and terms
of reuse in `GisVocabulary.ATTRIBUTION.md`). Two ways of adding them are
compared, built on GitHub by `evaluation/BuildVocabularyModels.py`:

- **distill-bge-base-gis**: a fresh model2vec distillation of
  bge-base-en-v1.5 with the words as whole tokens.
  - Its control, **distill-bge-base**, is the same distillation without
    them.
  - Both lack the further training (Tokenlearn) that made potion. The
    control separates that loss from the vocabulary's gain.
- **potion-base-8M-gis**: potion unchanged, plus one row per word.
  - Each row is the teacher's vector for the word, carried into potion's
    space by a linear map fitted on the tokens both vocabularies share.
  - It is given potion's median token length.

Both run through the plugin's own tokenizer and engine. Any of them could
ship as an ordinary model file, readable by released plugin versions too.

Language matrix. The plugin aims to serve 21 languages:

- English, French, Spanish, German, Italian and Portuguese;
- Norwegian (Bokmål and Nynorsk), Icelandic, Danish and Swedish;
- Polish, Slovenian, Slovak, Romanian, Bulgarian and Greek;
- Russian, Chinese, Japanese and Arabic.

The 40 needs are written in all of them (`matrixLanguages` in
`Queries.json`; translated by Claude, Icelandic and Nynorsk least certain).
For each pair of languages, the benchmark measures:

- the share of needs whose own translation is the most similar of the 40
  sentences in the other language;
- the cosine margin of matching over non-matching pairs.

It compares queries with each other, so it needs no relevance judgments.
The cross-language search scores above still use the original nine
languages.

Running it:

- Push a change to `evaluation/Candidates.json` or the workflow on a `dev/`
  branch.
- Or, once the workflow is on the default branch, start it by hand, choosing
  the candidates and universes.
- Locally, `make benchmark` runs only the `shipped` candidate. The others
  need `sentence-transformers` and `model2vec`, and download the models.
- The snapshot stays reachable through the tag `eval-snapshot-97fc1c9`. The
  `embeddings` branch itself is force pushed weekly.

## Reproduce or extend

```bash
make eval            # extracts the pinned snapshot, writes evaluation/Results.md and .json
make test            # includes the evaluation's own unit tests
```

- To change a judgment, edit `evaluation/Judgments.json`: 2 or 1 per plugin
  name, and anything absent is not relevant.
- To add a need, add it to `Queries.json` with its sentence in every
  language and its keyword list, then judge what every system and query form
  shows on its first screen. `judged@10` in `Results.md` must stay at 100 % for
  English.
- Better keyword lists come from real users: replace a `keywords` entry and
  rerun, then judge any new plugins it brings up.
- To evaluate a newer catalogue, change `EVAL_COMMIT` in the Makefile and the
  file names in `evaluation/SearchEvaluation.py`, then judge the new results
  the systems bring up. Results across snapshots are not comparable.
