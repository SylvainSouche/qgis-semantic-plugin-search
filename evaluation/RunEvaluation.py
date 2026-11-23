"""Run the search quality evaluation and write evaluation/Results.md and .json.

    python evaluation/RunEvaluation.py            # after `make eval-data`
    make eval                                     # both steps

Three parts, all on the pinned embeddings snapshot:

1. English, sentence against keyword list: every need asked as a sentence
   and as the keyword list a keyword search user types, on every backend,
   one shot and as an adaptive keyword session, QGIS 3 and QGIS 4
   catalogues, with paired bootstrap intervals.
2. Cross language: the same queries in eight more languages, judged against
   the same relevance judgments, plus tokenizer coverage and "language
   capture" (how many of the top ten results are written in the query's
   language rather than about the query's topic).
3. Non English catalogue: region specific needs whose plugins are often
   documented in the region's language, asked natively and in English.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from SearchEvaluation import (  # noqa: E402
    CUTOFF_NDCG,
    EVALUATION_DIR,
    EXPERIMENTS,
    METRICS,
    SNAPSHOT_COMMIT,
    SYSTEMS,
    Corpus,
    Systems,
    keywordSession,
    loadCorpus,
    loadJson,
    namesOf,
    pairedBootstrap,
    queryMetrics,
    textLanguage,
    tokenCoverage,
)

ALL_SYSTEMS = SYSTEMS + EXPERIMENTS
CROSS_SYSTEMS = ("bm25", "semantic", "hybrid", "fusion")
FILTERS = ("manager", "andfilter")
KEYWORD_SYSTEMS = ("manager", "andfilter", "bm25", "semantic", "hybrid", "fusion")
# One shot head to head comparisons: (system, form) a against b.
HEAD_TO_HEAD = (
    (("bm25", "keywords"), ("hybrid", "sentence")),
    (("andfilter", "keywords"), ("hybrid", "sentence")),
    (("bm25", "keywords"), ("hybrid", "keywords")),
    (("hybrid", "keywords"), ("hybrid", "sentence")),
    (("bm25", "sentence"), ("bm25", "keywords")),
    (("hybrid", "author sentence"), ("hybrid", "sentence")),
    (("bm25", "author keywords"), ("bm25", "keywords")),
)
COMPARISONS = (
    ("bm25", "hybrid"), ("bm25", "semantic"), ("semantic", "hybrid"),
    ("lexical", "hybrid"), ("hybrid", "fusion"), ("bm25", "fusion"),
)


def fullSizes(systems: Systems, keywords: list[str]) -> list[int]:
    """andfilter list length after each keyword, as typed in order."""
    return [len(systems.rankKeywords("andfilter", keywords[:k], depth=100000))
            for k in range(1, len(keywords) + 1)]


def evaluateRun(systems: Systems, system: str, texts: dict[str, str | list[str]],
                judgments: dict[str, dict[str, int]],
                judged: dict[str, set[str]] | None = None) -> dict[str, dict]:
    """Per query metrics, plus the share of the top ten that was judged.

    With judged, also an optimistic bound ("upper"): every unjudged plugin
    in the run's top ten counts as partly relevant (grade 1).
    """
    out = {}
    for qid, text in texts.items():
        positions = (systems.rankKeywords(system, text) if isinstance(text, list)
                     else systems.rank(system, text))
        names = namesOf(systems.corpus, positions)
        metrics = queryMetrics(names, judgments[qid])
        metrics["empty"] = 0.0 if names else 1.0
        if judged is not None:
            optimistic = dict(judgments[qid])
            for name in names[:CUTOFF_NDCG]:
                if name not in judged[qid]:
                    optimistic[name] = 1
            metrics["upper"] = queryMetrics(names, optimistic)["ndcg@10"]
        out[qid] = {"metrics": metrics, "top": names[:CUTOFF_NDCG]}
    return out


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def summary(run: dict[str, dict], qids: list[str]) -> dict[str, float]:
    keys = [*METRICS, "empty"] + (["upper"] if "upper" in run[qids[0]]["metrics"] else [])
    return {k: mean(run[q]["metrics"][k] for q in qids) for k in keys}


def judgedShare(run: dict[str, dict], qids: list[str], judged: dict[str, set[str]]) -> float:
    """Share of top ten results that are in the judged pool or judged relevant."""
    shown = [(q, n) for q in qids for n in run[q]["top"]]
    return mean(1.0 if n in judged[q] else 0.0 for q, n in shown) if shown else 1.0


def fmt(x: float) -> str:
    return f"{x:.3f}"


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def main() -> int:
    queries = loadJson("Queries.json")
    qrels = loadJson("Judgments.json")
    judgments: dict[str, dict[str, int]] = qrels["judgments"]
    judged = {q: set(qrels["pools"].get(q, [])) | set(judgments.get(q, {}))
              for q in judgments}
    languages = queries["languages"]
    taskQueries = [q for q in queries["queries"] if q["kind"] == "task"]
    taskIds = [q["id"] for q in taskQueries]
    mainIds = taskIds
    results: dict = {"snapshot": SNAPSHOT_COMMIT, "english": {}, "cross": {}, "native": {}}
    md: list[str] = ["# Search quality evaluation results", "",
                     f"Generated by `make eval` from embeddings snapshot `{SNAPSHOT_COMMIT[:12]}`. "
                     "Interpretation: docs/SearchQualityEvaluation.md.", ""]

    corpora: dict[str, Corpus] = {u: loadCorpus(u) for u in ("3", "4")}
    systemsBy = {u: Systems(c) for u, c in corpora.items()}

    # ------------------------------------------------------------ 1. English
    md += ["## 1. English: sentence against keyword list", "",
           "Each task need is asked as a sentence and as the keyword list a keyword search "
           "user would type, both written by "
           f"{queries['generator']['model']} ({queries['generator']['effort']} effort) from "
           "the task alone (evaluation/QueryPrompt.txt), blind to the catalogue. Both forms "
           "run on every backend: a keyword list can be typed into the semantic search box "
           "too. `author` rows are the evaluation author's own wording, kept for comparison. "
           "Judgments are per need, so every form is judged against the same expected "
           "plugins. `found@10`: a plugin "
           "that does the task is on the first screen; `precision@10`: share of the first "
           "screen (or of the whole list when shorter) that is relevant.", ""]
    english: dict[str, dict[str, dict]] = {}
    sessionsBy: dict[str, dict] = {}
    forms = {"sentence": {q["id"]: q["generated"]["sentence"] for q in taskQueries},
             "keywords": {q["id"]: q["generated"]["keywords"] for q in taskQueries},
             "first keyword": {q["id"]: q["generated"]["keywords"][:1] for q in taskQueries},
             "author sentence": {q["id"]: q["en"] for q in taskQueries},
             "author keywords": {q["id"]: q["authorKeywords"] for q in taskQueries}}
    for universe, systems in systemsBy.items():
        corpus = corpora[universe]
        md += [f"### QGIS {universe} catalogue ({int(corpus.visible.sum())} visible plugins "
               f"of {len(corpus.infos)}, {corpus.readmeCount} with a readme)", ""]
        runs = {(s, f): evaluateRun(systems, s, texts, judgments)
                for s in KEYWORD_SYSTEMS for f, texts in forms.items()}
        rows = []
        for s in KEYWORD_SYSTEMS:
            for f in forms:
                agg = summary(runs[s, f], taskIds)
                rows.append([s + (" *" if s in EXPERIMENTS else ""), f,
                             *(fmt(agg[m]) for m in ("ndcg@10", "found@10", "precision@10",
                                                      "recall@20", "mrr")),
                             fmt(agg["empty"]), fmt(judgedShare(runs[s, f], taskIds, judged))])
        md += ["**One shot**: the whole query typed at once.", "",
               table(["system", "query form", "nDCG@10", "found@10", "precision@10",
                      "recall@20", "MRR", "no result", "judged@10"], rows), ""]

        sessions = {s: {q["id"]: keywordSession(
                        lambda k, s=s, c=corpus, y=systems: namesOf(c, y.rankKeywords(
                            s, k, depth=100000 if s in FILTERS else 50)),
                        q["generated"]["keywords"], judgments[q["id"]]) for q in taskQueries}
                    for s in KEYWORD_SYSTEMS}
        sessionsBy[universe] = sessions
        rows = []
        for s in KEYWORD_SYSTEMS:
            out = sessions[s]
            rows.append([s + (" *" if s in EXPERIMENTS else ""), "keyword session",
                         fmt(mean(o.found for o in out.values())),
                         f"{mean(o.keywordsTyped for o in out.values()):.2f}",
                         fmt(mean(o.metrics["precision@10"] for o in out.values())),
                         fmt(mean(o.metrics["ndcg@10"] for o in out.values())),
                         fmt(mean(any(not st.kept for st in o.steps) for o in out.values()))])
        for s in ("semantic", "hybrid"):
            agg = summary(runs[s, "sentence"], taskIds)
            rows.append([s, "sentence, one shot", fmt(agg["found@10"]), "–",
                         fmt(agg["precision@10"]), fmt(agg["ndcg@10"]), fmt(agg["empty"])])
        md += ["**Adaptive keyword session**: type the first keyword, read the first screen, "
               "stop if it shows a plugin that does the task, otherwise add the next keyword; "
               "a keyword that empties the list is taken back out. Measured on the screen the "
               "session stops on.", "",
               table(["system", "how", "found", "keywords typed", "precision@10", "nDCG@10",
                      "hit an empty list"], rows), ""]

        rows = []
        for (sa, fa), (sb, fb) in HEAD_TO_HEAD:
            for metric in ("ndcg@10", "precision@10", "found@10"):
                va = [runs[sa, fa][q]["metrics"][metric] for q in taskIds]
                vb = [runs[sb, fb][q]["metrics"][metric] for q in taskIds]
                d, lo, hi = pairedBootstrap(va, vb)
                rows.append([f"{sb} {fb} vs {sa} {fa}", metric, f"{d:+.3f}",
                             f"[{lo:+.3f}, {hi:+.3f}]",
                             f"{sum(y > x for x, y in zip(va, vb))} / "
                             f"{sum(y < x for x, y in zip(va, vb))}"])
        for sa in ("bm25", "andfilter"):
            for metric in ("precision@10", "found@10"):
                va = [sessions[sa][q].metrics[metric] for q in taskIds]
                vb = [runs["hybrid", "sentence"][q]["metrics"][metric] for q in taskIds]
                d, lo, hi = pairedBootstrap(va, vb)
                rows.append([f"hybrid sentence vs {sa} keyword session", metric, f"{d:+.3f}",
                             f"[{lo:+.3f}, {hi:+.3f}]",
                             f"{sum(y > x for x, y in zip(va, vb))} / "
                             f"{sum(y < x for x, y in zip(va, vb))}"])
        md += ["Paired differences over the 40 needs (b − a, 95 % bootstrap interval):", "",
               table(["comparison", "metric", "mean diff", "95 % CI", "wins / losses"], rows), ""]

        # every system on sentences, as before
        sentenceRuns = {s: evaluateRun(systems, s, forms["sentence"], judgments)
                        for s in ALL_SYSTEMS}
        english[universe] = sentenceRuns
        rows = []
        for s in ALL_SYSTEMS:
            agg = summary(sentenceRuns[s], taskIds)
            rows.append([s + (" *" if s in EXPERIMENTS else ""),
                         *(fmt(agg[m]) for m in METRICS), fmt(agg["empty"]),
                         fmt(judgedShare(sentenceRuns[s], taskIds, judged))])
        md += ["**Every system on the sentences**", "",
               table(["system", *METRICS, "no result", "judged@10"], rows), ""]
        rows = []
        for a, b in COMPARISONS:
            d, lo, hi = pairedBootstrap([sentenceRuns[a][q]["metrics"]["ndcg@10"] for q in taskIds],
                                        [sentenceRuns[b][q]["metrics"]["ndcg@10"] for q in taskIds])
            rows.append([f"{b} vs {a}", f"{d:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]"])
        md += [table(["sentences, nDCG@10", "mean diff", "95 % CI"], rows), "",
               "\\* not shipped, measured for comparison.", ""]
        results["english"][universe] = {
            "oneShot": {f"{s}/{f}": {"summary": summary(runs[s, f], taskIds),
                                     "perQuery": {q: runs[s, f][q]["metrics"] for q in taskIds}}
                        for s in KEYWORD_SYSTEMS for f in forms},
            "sessions": {s: {q: {"found": o.found, "keywordsTyped": o.keywordsTyped,
                                 "steps": [{"keywords": st.keywords, "size": st.size,
                                            "kept": st.kept, "shown": st.shown}
                                           for st in o.steps],
                                 **o.metrics}
                             for q, o in sessions[s].items()} for s in KEYWORD_SYSTEMS},
            "sentences": {s: {"summary": summary(sentenceRuns[s], taskIds),
                              "perQuery": {q: sentenceRuns[s][q]["metrics"] for q in taskIds}}
                          for s in ALL_SYSTEMS},
        }
        english[universe + "/runs"] = runs

    runs3, sessions3 = english["3/runs"], sessionsBy["3"]

    def sessionCell(o):
        if not o.found:
            return "✗"
        return str(len([st for st in o.steps if st.kept]))

    md += ["### Per need, QGIS 3 catalogue", "",
           "nDCG@10 of each query form, then the keyword session: number of keywords kept "
           "when a plugin that does the task appeared, ✗ if it never did. `filter size` is "
           "the andfilter list length after each keyword.", "",
           table(["need", "keywords", "hybrid sentence", "hybrid keywords", "bm25 keywords",
                  "andfilter keywords", "session bm25", "session hybrid", "session andfilter",
                  "filter size", "sentence"],
                 [[q["id"], " + ".join(q["generated"]["keywords"]),
                   fmt(runs3["hybrid", "sentence"][q["id"]]["metrics"]["ndcg@10"]),
                   fmt(runs3["hybrid", "keywords"][q["id"]]["metrics"]["ndcg@10"]),
                   fmt(runs3["bm25", "keywords"][q["id"]]["metrics"]["ndcg@10"]),
                   fmt(runs3["andfilter", "keywords"][q["id"]]["metrics"]["ndcg@10"]),
                   sessionCell(sessions3["bm25"][q["id"]]),
                   sessionCell(sessions3["hybrid"][q["id"]]),
                   sessionCell(sessions3["andfilter"][q["id"]]),
                   " → ".join(str(n) for n in
                              fullSizes(systemsBy["3"], q["generated"]["keywords"])),
                   q["generated"]["sentence"]]
                  for q in taskQueries]), ""]

    # ------------------------------------------------------------ 2. Cross language
    corpus3, systems3 = corpora["3"], systemsBy["3"]
    md += ["## 2. Cross language: the same needs asked in other languages", "",
           "Same judgments as English. QGIS 3 catalogue. `vs en` is the share of the English "
           "nDCG@10 kept. `unk` is the share of words the English WordPiece vocabulary cannot "
           "represent at all (dropped silently), `pieces` the average pieces per word "
           "(1.0 means whole words are known). `same-lang@10` is the share of the top ten "
           "results whose own text is written in the query language.", ""]
    pluginLanguage = [textLanguage(t) for t in corpus3.texts]
    position = {name: i for i, name in enumerate(i.name for i in corpus3.infos)}
    langToTag = {"en": "en", "fr": "fr", "de": "de", "es": "es", "pt": "pt", "it": "it",
                 "ru": "ru", "zh": "cjk", "ja": "cjk"}
    baseline = Counter(pluginLanguage)
    crossRows, crossJson = [], {}
    for lang in languages:
        texts = {q["id"]: q[lang] for q in queries["queries"]}
        perSystem = {s: evaluateRun(systems3, s, texts, judgments, judged)
                     for s in CROSS_SYSTEMS}
        coverage = [tokenCoverage(corpus3, t) for t in texts.values()]
        tag = langToTag[lang]
        capture = mean(
            mean(1.0 if pluginLanguage[position[n]] == tag else 0.0
                 for n in perSystem["hybrid"][q]["top"]) if perSystem["hybrid"][q]["top"] else 0.0
            for q in mainIds)
        row = [lang]
        entry = {"coverage": {"unk": mean(c["unk"] for c in coverage),
                              "pieces": mean(c["pieces"] for c in coverage)},
                 "sameLanguageTop10": capture,
                 "catalogueShare": baseline[tag] / len(pluginLanguage)}
        for s in CROSS_SYSTEMS:
            agg = summary(perSystem[s], mainIds)
            en = results["english"]["3"]["sentences"][s]["summary"]["ndcg@10"]
            entry[s] = {**agg, "keptVsEnglish": agg["ndcg@10"] / en if en else 0.0,
                        "judged@10": judgedShare(perSystem[s], mainIds, judged)}
            row += [f"{fmt(agg['ndcg@10'])}–{fmt(agg['upper'])}",
                    f"{entry[s]['keptVsEnglish']:.0%}"]
        row += [f"{entry['coverage']['unk']:.0%}", f"{entry['coverage']['pieces']:.2f}",
                f"{capture:.0%}", f"{entry['catalogueShare']:.1%}",
                f"{entry['hybrid']['judged@10']:.0%}"]
        crossRows.append(row)
        crossJson[lang] = entry
    header = ["lang"]
    for s in CROSS_SYSTEMS:
        header += [f"{s} nDCG@10", "vs en"]
    header += ["unk", "pieces", "same-lang@10 (hybrid)", "catalogue share", "judged@10 (hybrid)"]
    md += ["nDCG@10 is given as a range: judged value – optimistic bound where every "
           "unjudged result in the top ten counts as partly relevant. `vs en` uses the "
           "judged value.", "", table(header, crossRows), ""]
    results["cross"] = crossJson

    # examples of language capture
    md += ["Hybrid top five for one need in each language (T01, contour lines):", ""]
    t01 = next(q for q in queries["queries"] if q["id"] == "T01")
    for lang in languages:
        top = namesOf(corpus3, systems3.rank("hybrid", t01[lang]))[:5]
        marks = ["**" + n + "**" if judgments["T01"].get(n, 0) > 0 else n for n in top]
        md.append(f"- {lang} `{t01[lang]}`: " + ", ".join(marks))
    md += ["", "Bold: judged relevant.", ""]

    # ------------------------------------------------------------ 3. Native
    md += ["## 3. Non English catalogue: region specific needs", "",
           "Each need asked in the region's language (native) and in English. "
           "`doc-lang share` is the share of the judged relevant plugins whose own text is "
           "mainly in the query language rather than English.", ""]
    native = queries["native"]
    nativeTexts = {q["id"]: q["text"] for q in native}
    englishTexts = {q["id"]: q["en"] for q in native}
    nativeIds = [q["id"] for q in native]
    rows, nativeJson = [], {}
    for s in CROSS_SYSTEMS:
        nat = evaluateRun(systems3, s, nativeTexts, judgments)
        eng = evaluateRun(systems3, s, englishTexts, judgments)
        nativeJson[s] = {"native": summary(nat, nativeIds), "english": summary(eng, nativeIds),
                         "perQuery": {q: {"native": nat[q]["metrics"]["ndcg@10"],
                                          "english": eng[q]["metrics"]["ndcg@10"]}
                                      for q in nativeIds}}
        rows.append([s, fmt(nativeJson[s]["native"]["ndcg@10"]),
                     fmt(nativeJson[s]["english"]["ndcg@10"]),
                     fmt(nativeJson[s]["native"]["success@5"]),
                     fmt(nativeJson[s]["english"]["success@5"])])
    md += [table(["system", "native nDCG@10", "english nDCG@10", "native success@5",
                  "english success@5"], rows), ""]
    perRows = []
    for q in native:
        rel = [n for n, g in judgments[q["id"]].items() if g > 0 and n in position]
        docShare = mean(1.0 if pluginLanguage[position[n]] == langToTag[q["lang"]] else 0.0
                        for n in rel)
        perRows.append([q["id"], q["lang"], f"{docShare:.0%}",
                        *(fmt(nativeJson[s]["perQuery"][q["id"]][k])
                          for s in ("bm25", "hybrid") for k in ("native", "english")),
                        q["text"]])
    md += [table(["query", "lang", "doc-lang share", "bm25 native", "bm25 en",
                  "hybrid native", "hybrid en", "text"], perRows), ""]
    results["native"] = nativeJson

    catalogue = Counter(pluginLanguage)
    md += ["## Catalogue language mix (QGIS 3, embedded text, coarse detection)", "",
           table(["language", "plugins", "share"],
                 [[k, str(v), f"{v / len(pluginLanguage):.1%}"]
                  for k, v in catalogue.most_common()]), ""]
    results["catalogueLanguages"] = dict(catalogue)

    (EVALUATION_DIR / "Results.md").write_text("\n".join(md), encoding="utf-8")
    (EVALUATION_DIR / "Results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
