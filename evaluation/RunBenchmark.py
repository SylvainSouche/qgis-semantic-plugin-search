"""Benchmark one embedding model on the search quality evaluation.

    python evaluation/RunBenchmark.py --candidate potion-base-32M --out build/benchmark
    make benchmark CANDIDATES="shipped potion-base-32M"

Runs in the BenchmarkEmbeddings GitHub workflow, one job per model, so no
model is downloaded on a developer machine. The candidate's model embeds
exactly the plugin text of the pinned snapshot (Candidates.json lists the
models); the keyword systems, needs, queries and judgments are those of
`make eval`. The semantic and hybrid systems use the candidate's vectors;
the hybrid adds the shipped lexical boost unchanged.

Writes <out>/<candidate>.json with the metrics, and <out>/<candidate>.unjudged.json
with every plugin the candidate shows on a first screen that was never
judged. Those need judging (add them to Judgments.json) before the
candidate's numbers are exact; until then judged@10 says how much is known
and the `upper` value counts every unjudged plugin as partly relevant.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from RunEvaluation import evaluateRun, judgedShare, mean, summary  # noqa: E402
from SearchEvaluation import (  # noqa: E402
    CUTOFF_NDCG,
    REPO_ROOT,
    SNAPSHOT_COMMIT,
    Corpus,
    EncodedVectors,
    Systems,
    keywordSession,
    loadCorpus,
    loadJson,
    namesOf,
    textLanguage,
)

BATCH = 64
LANGUAGE_TAG = {"en": "en", "fr": "fr", "de": "de", "es": "es", "pt": "pt", "it": "it",
                "ru": "ru", "zh": "cjk", "ja": "cjk"}


def candidateById(candidateId: str) -> dict:
    for candidate in loadJson("Candidates.json")["candidates"]:
        if candidate["id"] == candidateId:
            return candidate
    raise SystemExit(f"unknown candidate {candidateId!r}: see evaluation/Candidates.json")


def buildVectors(candidate: dict, corpus: Corpus) -> tuple[EncodedVectors, dict]:
    """Embed the corpus with the candidate; return the vectors and model facts."""
    kind = candidate["kind"]
    started = time.perf_counter()
    if kind == "shipped":
        vectors = EncodedVectors(corpus.store.embeddings(), corpus.engine.embedQuery)
        facts = {"parameters": len(corpus.model.vocabulary()) * int(vectors.documents.shape[1]),
                 "revision": SNAPSHOT_COMMIT}
    elif kind == "npz":
        from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel  # noqa: PLC0415
        from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine  # noqa: PLC0415
        from SemanticPluginSearch.Domain.WordPieceTokenizer import WordPieceTokenizer  # noqa: PLC0415

        path = REPO_ROOT / "build" / "vocabulary-models" / f"{candidate['id']}.npz"
        model = NpzStaticModel.load(path)
        engine = StaticEmbeddingEngine(WordPieceTokenizer(model.vocabulary()), model)
        vectors = EncodedVectors(np.stack([engine.embedQuery(t) for t in corpus.texts]),
                                 engine.embedQuery)
        built = path.with_suffix(".facts.json")
        facts = {"parameters": len(model.vocabulary()) * model.dimension(),
                 **(json.loads(built.read_text()) if built.is_file() else {})}
    elif kind == "model2vec":
        from model2vec import StaticModel  # noqa: PLC0415

        model = StaticModel.from_pretrained(candidate["model"])
        documents = model.encode(corpus.texts, batch_size=BATCH)
        vectors = EncodedVectors(documents, lambda text: model.encode([text])[0])
        facts = {"parameters": int(np.prod(model.embedding.shape))}
    elif kind == "sentence-transformers":
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model = SentenceTransformer(candidate["model"], device="cpu",
                                    truncate_dim=candidate.get("dim"))
        queryPrefix = candidate.get("queryPrefix", "")
        documentPrefix = candidate.get("documentPrefix", "")
        documents = model.encode([documentPrefix + t for t in corpus.texts], batch_size=BATCH,
                                 normalize_embeddings=True, show_progress_bar=False)
        vectors = EncodedVectors(
            documents,
            lambda text: model.encode([queryPrefix + text], normalize_embeddings=True,
                                      show_progress_bar=False)[0])
        facts = {"parameters": int(sum(p.numel() for p in model.parameters())),
                 "maxSequenceLength": getattr(model, "max_seq_length", None)}
    else:
        raise SystemExit(f"unknown candidate kind {kind!r}")
    facts["documentSeconds"] = round(time.perf_counter() - started, 1)
    facts["dimensions"] = int(vectors.documents.shape[1])
    if kind not in ("shipped", "npz"):
        facts["revision"] = resolvedRevision(candidate["model"])
    elif kind == "npz":
        facts["revision"] = resolvedRevision(candidate["teacher"])
    return vectors, facts


def resolvedRevision(modelId: str) -> str | None:
    """The Hugging Face commit the model was downloaded at, for the record."""
    try:
        from huggingface_hub import HfApi  # noqa: PLC0415

        return HfApi().model_info(modelId).sha
    except Exception:  # noqa: BLE001 - recording only; offline is not an error
        return None


def queryMilliseconds(vectors: EncodedVectors, texts: list[str]) -> float:
    started = time.perf_counter()
    for text in texts:
        vectors._encode(text)
    return round(1000 * (time.perf_counter() - started) / max(len(texts), 1), 2)


def languageMatrix(vectors: EncodedVectors, tasks: list[dict], languages: list[str]) -> dict:
    """How well the model aligns the same need across query languages.

    For each pair (a, b): top1 is the share of needs whose sentence in a has
    its own translation in b as the most similar of the needs' sentences in
    b; margin is the mean cosine of matching pairs minus the mean cosine of
    the other pairs. A language aligned with itself scores top1 1.0.
    """
    embedded = {}
    for lang in languages:
        rows = [vectors.query(q[lang]) for q in tasks]
        embedded[lang] = np.stack([r if r is not None else np.zeros(vectors.documents.shape[1])
                                   for r in rows])
    out: dict = {}
    count = len(tasks)
    for a in languages:
        out[a] = {}
        for b in languages:
            similarity = embedded[a] @ embedded[b].T
            top1 = float(np.mean(np.argmax(similarity, axis=1) == np.arange(count)))
            matching = float(np.mean(np.diag(similarity)))
            others = float((similarity.sum() - np.trace(similarity)) / (count * count - count))
            out[a][b] = {"top1": round(top1, 3), "margin": round(matching - others, 3)}
    return out


def benchmarkUniverse(candidate: dict, universe: str, queries: dict, judgments: dict,
                      judged: dict) -> tuple[dict, dict, list]:
    corpus = loadCorpus(universe)
    vectors, facts = buildVectors(candidate, corpus)
    systems = Systems(corpus, vectors)
    tasks = [q for q in queries["queries"] if q["kind"] == "task"]
    ids = [q["id"] for q in tasks]
    forms = {"sentence": {q["id"]: q["generated"]["sentence"] for q in tasks},
             "keywords": {q["id"]: q["generated"]["keywords"] for q in tasks},
             "author sentence": {q["id"]: q["en"] for q in tasks}}
    facts["queryMilliseconds"] = queryMilliseconds(vectors, [q["en"] for q in tasks])
    out: dict = {"english": {}, "facts": facts}
    shown: list[tuple[str, str]] = []
    for system in ("semantic", "hybrid", "fusion"):
        for form, texts in forms.items():
            run = evaluateRun(systems, system, texts, judgments, judged)
            out["english"][f"{system}/{form}"] = {
                **summary(run, ids), "judged@10": judgedShare(run, ids, judged)}
            shown += [(q, n) for q in ids for n in run[q]["top"]]
    sessions = [keywordSession(lambda k: namesOf(corpus, systems.rankKeywords("hybrid", k)),
                               q["generated"]["keywords"], judgments[q["id"]]) for q in tasks]
    out["hybridSession"] = {"found": mean(o.found for o in sessions),
                            "keywordsTyped": mean(o.keywordsTyped for o in sessions),
                            "precision@10": mean(o.metrics["precision@10"] for o in sessions)}
    if universe == "3":
        pluginLanguage = [textLanguage(t) for t in corpus.texts]
        position = {info.name: i for i, info in enumerate(corpus.infos)}
        out["languageMatrix"] = languageMatrix(
            vectors, tasks, queries.get("matrixLanguages", queries["languages"]))
        out["cross"] = {}
        for lang in queries["languages"]:
            texts = {q["id"]: q[lang] for q in tasks}
            run = evaluateRun(systems, "hybrid", texts, judgments, judged)
            agg = summary(run, ids)
            capture = mean(mean(1.0 if pluginLanguage[position[n]] == LANGUAGE_TAG[lang] else 0.0
                                for n in run[q]["top"]) if run[q]["top"] else 0.0 for q in ids)
            out["cross"][lang] = {"ndcg@10": agg["ndcg@10"], "upper": agg["upper"],
                                  "sameLanguageTop10": capture,
                                  "judged@10": judgedShare(run, ids, judged)}
            shown += [(q, n) for q in ids for n in run[q]["top"]]
        native = queries["native"]
        nativeIds = [q["id"] for q in native]
        for key, field in (("native", "text"), ("nativeInEnglish", "en")):
            run = evaluateRun(systems, "hybrid", {q["id"]: q[field] for q in native},
                              judgments, judged)
            out[key] = {**summary(run, nativeIds), "judged@10": judgedShare(run, nativeIds, judged)}
            shown += [(q, n) for q in nativeIds for n in run[q]["top"]]
    unjudged = sorted({(q, n) for q, n in shown if n not in judged[q]})
    infoByName = {info.name: info for info in corpus.infos}
    pending = [{"query": q, "plugin": n, "universe": universe,
                "description": (infoByName[n].description or "")[:300],
                "tags": list(infoByName[n].tags)[:8]} for q, n in unjudged]
    return out, facts, pending


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--universes", default="3", help="space separated, e.g. '3 4'")
    parser.add_argument("--out", default="build/benchmark")
    args = parser.parse_args(argv)
    candidate = candidateById(args.candidate)
    queries = loadJson("Queries.json")
    qrels = loadJson("Judgments.json")
    judgments = qrels["judgments"]
    judged = {q: set(qrels["pools"].get(q, [])) | set(judgments[q]) for q in judgments}
    result: dict = {"candidate": candidate, "snapshot": SNAPSHOT_COMMIT,
                    "cutoff": CUTOFF_NDCG, "python": platform.python_version(), "universes": {}}
    pending: list = []
    for universe in args.universes.split():
        out, facts, unjudged = benchmarkUniverse(candidate, universe, queries, judgments, judged)
        result["universes"][universe] = out
        result.setdefault("facts", facts)
        pending += unjudged
    outDir = Path(args.out)
    outDir.mkdir(parents=True, exist_ok=True)
    (outDir / f"{candidate['id']}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (outDir / f"{candidate['id']}.unjudged.json").write_text(
        json.dumps(pending, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    english = result["universes"][args.universes.split()[0]]["english"]
    sentence = english["hybrid/sentence"]
    print(f"{candidate['id']}: hybrid sentence nDCG@10 {sentence['ndcg@10']:.3f}, "
          f"judged@10 {sentence['judged@10']:.0%}, {len(pending)} unjudged pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
