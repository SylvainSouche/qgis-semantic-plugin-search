# Search quality evaluation (0.5 development)

Two questions, asked on 2026-11-12 at the start of the 0.5 line:

1. Is the shipped search really better than pure keyword search?
2. How well does it work across languages: a non English query, or a plugin
   documented in another language?

The numbers below come from `evaluation/Results.md`, regenerated with
`make eval`. This page interprets them.

## Short answers

**Against keyword search.** The shipped hybrid ranking is the best of the
systems measured, but only slightly better than a properly built keyword
search. On the QGIS 3 catalogue it scores nDCG@10 0.568 against 0.528 for
BM25 over the same plugin text: +0.040, with a 95 % interval of −0.007 to
+0.085. On QGIS 4 the gap is +0.033 (−0.002 to +0.069). Both intervals cross
zero. Where it clearly wins is the first result: mean reciprocal rank is 0.925
against 0.828, and a relevant plugin appears in the top five for 100 % of
queries against 95.8 %. The semantic part alone is not better than BM25
(−0.037). The value comes from adding the lexical boost to it, not from the
embeddings alone.

Against what QGIS users actually have, the plugin manager's search box, the
difference is total: the manager's phrase filter (approximated here) finds
nothing for any of the 40 task descriptions and for 83 % of all queries.

So `asm-static-quality` ("clearly better than keyword matching") holds against
the plugin manager filter but is **not supported against a real keyword ranker**.

**Across languages.** Search effectively works in English only.

- Asked in French, German, Spanish, Portuguese or Italian, the same 48 needs
  keep 17–29 % of their English nDCG@10. Even counting every unjudged result as
  relevant, they stay below 0.28 against 0.57 in English.
- Russian and Japanese queries get almost nothing (0.002 and 0.024). Chinese
  keeps 23 %.
- The failure has a clear mechanism: **the model matches the query's language,
  not its meaning.** 58–72 % of the top ten results for a European-language
  query are plugins written in that language, whatever their topic, although
  those plugins are only 1–4 % of the catalogue. Asked in French for contour
  lines, the top results are a French watershed tool and two French data
  portals.
- BM25 fails the same way, so this is not a regression of the embeddings.
  Neither approach bridges languages.

**Non English plugins.** About 18 % of the QGIS 3 catalogue (≈ 710 plugins) is
documented mainly in another language: Portuguese, Japanese and Chinese,
Spanish, French, German, Italian, Russian and Korean. For regional needs, such
as cadastres, national data portals and registries, asking in the region's
language works well (hybrid nDCG@10 0.624). Asking the same need in English
works worse with the hybrid ranking (0.413) than with BM25 (0.550), because
English wording only reaches those plugins through literal proper nouns
(IBGE, ALKIS, SIGEF, Tianditu), which BM25 weighs more heavily.

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
| bm25 | Okapi BM25 over the embedded text (name, description, about, tags, readme excerpt) |
| bm25stem | the same with a light English suffix stripper |
| lexical | the shipped lexical boost alone (`Domain/LexicalBoost.py`) |
| semantic | the shipped static embedding cosine alone |
| hybrid | the shipped ranking (`Domain/SearchEngine.py`) |
| fusion | not shipped: reciprocal rank fusion of semantic and BM25, as a comparison |

**Queries** (`evaluation/Queries.json`):

- 40 task descriptions of the kind the search box invites, such as "draw
  isochrones of the area reachable within 10 minutes by car".
- 8 one word keyword queries.
- 16 region specific "native" needs.

Every task and keyword query carries hand translations into French, German,
Spanish, Portuguese, Italian, Russian, Chinese and Japanese.

**Judgments** (`evaluation/Judgments.json`) are graded: 2 means the plugin
does the task, 1 means it does so partly, for one region or data source only,
or as a side feature.

- Candidates were pooled from the top results of every system and language,
  listed alphabetically without saying which system found them.
- A pattern search over the whole catalogue then found plugins no system had
  retrieved. It recovered real misses: qgis2web, Lizmap and QGIS Cloud for the
  web map query, and ORS Tools for routing and isochrones.
- 1,075 relevant plugins in all, a median of 15 per query.
- Every English run has 100 % of its top ten judged. Cross language runs have
  50–66 % judged. Their results are therefore given as a range: the judged value,
  and an optimistic bound where every unjudged result counts as relevant.

**Metrics.**

- nDCG@10 is the headline. It is graded and rewards putting the best plugins first.
- Recall@20, MRR and Success@5 are also reported.
- Comparisons between two systems use a paired bootstrap over queries (10,000
  resamples) and give a 95 % interval.

**Limitations to keep in mind.**

- One judge: Claude, reading names, descriptions, about texts and tags.
  `Judgments.json` is plain JSON so it can be reviewed and corrected, and
  `make eval` recomputes everything.
- 48 main queries detect differences of about ±0.05 nDCG@10. Smaller
  differences are noise at this size.
- The manager baseline reproduces the plugin manager's phrase filter from
  memory of its behaviour, not from its source.
- Translations are by Claude. Plugin languages are detected with a coarse
  stopword heuristic.

## Where each approach wins (QGIS 3, nDCG@10)

The hybrid ranking clearly beats BM25 when the user's words differ from the
plugin's:

| query | hybrid | bm25 |
|---|---|---|
| simulate river flooding and inundation depth | 0.630 | 0.273 |
| process a lidar point cloud into a digital terrain model | 0.570 | 0.258 |
| compute NDVI from Sentinel-2 bands | 0.575 | 0.357 |
| analyse public transport timetables from GTFS | 0.779 | 0.396 |
| export the attribute table to an Excel spreadsheet | 0.620 | 0.261 |
| manage and edit the metadata of my layers | 0.420 | 0.157 |

BM25 wins when one distinctive word carries the need and the embedding
average dilutes it:

| query | hybrid | bm25 |
|---|---|---|
| animate a layer over time with a time slider | 0.325 | 0.734 |
| match GPS points to the roads they were recorded on | 0.129 | 0.370 |
| check topology errors in a polygon layer | 0.572 | 0.752 |
| split a polygon into parts of equal area | 0.718 | 0.905 |
| estimate the solar potential of rooftops | 0.375 | 0.544 |

Three queries are hard for every system:

- "interpolate temperature measurements": 0.06 or less everywhere. Plugins
  about thermal imagery outrank the interpolation tools.
- "classify a drone orthophoto": about 0.18.
- "draw an elevation profile": about 0.26.

The fusion experiment does not beat the shipped hybrid on nDCG@10 (−0.009).
It finds more relevant plugins in the top twenty (recall@20 0.508 against
0.473) but puts a relevant one first less often. Simply bolting BM25 on
through rank fusion is therefore not an improvement.

## Cross language detail (QGIS 3)

| query language | hybrid nDCG@10 | share of English | top ten in the query language | words unknown to the vocabulary | WordPiece pieces per word |
|---|---|---|---|---|---|
| en | 0.568 | 100 % | 97 % | 0 % | 1.30 |
| fr | 0.166–0.271 | 29 % | 70 % | 0 % | 1.83 |
| es | 0.127–0.232 | 22 % | 72 % | 0 % | 2.05 |
| pt | 0.123–0.236 | 22 % | 63 % | 0 % | 2.11 |
| de | 0.110–0.217 | 19 % | 66 % | 0 % | 2.83 |
| it | 0.097–0.190 | 17 % | 58 % | 0 % | 2.19 |
| zh | 0.132–0.224 | 23 % | 48 % | 75 % | 1.04 |
| ja | 0.024–0.151 | 4 % | 88 % | 48 % | 2.31 |
| ru | 0.002–0.133 | 0 % | 100 % | 0 % | 6.39 |

The vocabulary is the English BERT WordPiece of all-MiniLM-L6-v2, and it
explains the three regimes:

- **Latin script European languages** are never unknown but are cut into 2–3
  fragments per word. Those fragments carry the "French-ness" of the text far
  more than its topic.
- **Russian** falls apart into single characters (6.4 pieces per word). That
  is a pure script signal, so it only ever matches Russian plugins.
- **Chinese and Japanese** lose half or more of their characters to unknown
  tokens. Chinese does a little better because the surviving characters are
  meaningful one by one.

## What this means for 0.5

These are options to decide, not decisions.

1. **Correct the claim.** The README says plugins are ranked "by how well it
   matches" and the assumption says "clearly better than keyword matching".
   An honest claim is "far better than the plugin manager's search, on a par
   with good keyword search for typical queries, better at putting the right
   plugin first". Settling `asm-static-quality` is a user decision.
2. **Keyword side.** BM25 alone matches the hybrid on nDCG@10. A BM25 based
   lexical component, normalised into the hybrid score instead of the current
   fixed boosts, deserves a measured trial. Rank fusion was tried and did not
   help.
3. **Multilingual** (`cand-multilingual-model`). The problem is the model, not
   the ranking code. Any fix has to bring a cross lingual vocabulary within the
   constraints `con-light-engine` and `con-commercial-models`, for example a
   multilingual static model distilled from a commercially licensed
   multilingual sentence model, pruned to a reasonable download size. The
   other route is translating plugin texts on the GitHub side. The cross
   language part of this evaluation is the yardstick for either.
4. **Keep the harness.** `cand-golden-query-eval` asked for exactly this. It
   now exists as `make eval`; running it in the weekly workflow is still open.

## Reproduce or extend

```bash
make eval            # extracts the pinned snapshot, writes evaluation/Results.md and .json
make test            # includes the evaluation's own unit tests
```

- To change a judgment, edit `evaluation/Judgments.json`: 2 or 1 per plugin
  name, and anything absent is not relevant.
- To add a query, add it to `Queries.json` with all languages, then judge its
  results.
- To evaluate a newer catalogue, change `EVAL_COMMIT` in the Makefile and the
  file names in `evaluation/SearchEvaluation.py`, then judge the new results
  the systems bring up. Results across snapshots are not comparable.
