"""Build the static models that add GIS words, for the embedding benchmark.

    python evaluation/BuildVocabularyModels.py --candidate potion-base-8M-gis

Runs in the BenchmarkEmbeddings workflow (it downloads the teacher model),
and writes build/vocabulary-models/<candidate>.npz in the shipped .npz
format (int8), so RunBenchmark loads it with the plugin's own tokenizer and
engine, exactly as it would ship. Candidates (evaluation/Candidates.json):

- build "distill": a fresh model2vec distillation of the teacher, with the
  extra words of the candidate's vocabulary file when it names one. Without
  vocabulary it is the control: what plain distillation gives without
  potion's further training (Tokenlearn).
- build "append": potion-base-8M itself, unchanged, plus one new row per
  extra word. The teacher embeds each word; a linear map, fitted on the
  tokens both vocabularies share, carries it into potion's space; the row
  gets potion's median token length (potion encodes word weight in length).
"""
from __future__ import annotations

import argparse
import csv
import inspect
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from SearchEvaluation import EVALUATION_DIR, REPO_ROOT, SNAPSHOT_DIR, SNAPSHOT_FILES  # noqa: E402

from pipeline.ConvertStaticModel import writeNpz  # noqa: E402
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel  # noqa: E402
from SemanticPluginSearch.Domain.WordPieceTokenizer import WordPieceTokenizer  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "build" / "vocabulary-models"


def readVocabulary(name: str) -> list[str]:
    with (EVALUATION_DIR / name).open(encoding="utf-8") as stream:
        return [row["word"] for row in csv.DictReader(stream, delimiter="\t")]


def distill(teacher: str, vocabulary: list[str] | None, pcaDims: int | None):
    from model2vec.distill import distill as m2vDistill  # noqa: PLC0415

    kwargs = {"model_name": teacher, "vocabulary": vocabulary, "pca_dims": pcaDims}
    if "use_subword" in inspect.signature(m2vDistill).parameters:
        kwargs["use_subword"] = True
    model = m2vDistill(**kwargs)
    return list(model.tokens), np.asarray(model.embedding, dtype=np.float32)


def buildDistilled(candidate: dict, words: list[str]) -> tuple[list[str], np.ndarray, dict]:
    tokens, vectors = distill(candidate["teacher"], words or None, 256)
    return tokens, vectors, {"method": "model2vec distill, PCA 256"}


def buildAppended(candidate: dict, words: list[str]) -> tuple[list[str], np.ndarray, dict]:
    potion = NpzStaticModel.load(SNAPSHOT_DIR / SNAPSHOT_FILES["model"])
    potionTokens = sorted(potion.vocabulary(), key=potion.vocabulary().get)
    potionVectors = potion.vectors()
    teacherTokens, teacherVectors = distill(candidate["teacher"], words, None)
    teacherIndex = {token: i for i, token in enumerate(teacherTokens)}
    shared = [(i, teacherIndex[t]) for i, t in enumerate(potionTokens)
              if t in teacherIndex and np.any(potionVectors[i])]

    def unit(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.where(norms > 0, norms, 1.0)

    source = unit(teacherVectors[[t for _, t in shared]])
    target = unit(potionVectors[[p for p, _ in shared]])
    rng = np.random.default_rng(20261112)
    held = rng.random(len(shared)) < 0.1
    mapping, *_ = np.linalg.lstsq(source[~held], target[~held], rcond=None)
    check = unit(source[held] @ mapping)
    fit = float(np.mean(np.sum(check * target[held], axis=1)))
    mapping, *_ = np.linalg.lstsq(source, target, rcond=None)
    known = set(potionTokens)
    added = [w for w in words if w not in known and w in teacherIndex]
    length = float(np.median(np.linalg.norm(potionVectors, axis=1)))
    rows = unit(teacherVectors[[teacherIndex[w] for w in added]] @ mapping) * length
    return (potionTokens + added, np.vstack([potionVectors, rows]),
            {"method": "potion-base-8M plus mapped rows", "mapFitHeldOutCosine": round(fit, 4),
             "sharedTokens": len(shared)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    candidates = json.loads((EVALUATION_DIR / "Candidates.json").read_text())["candidates"]
    candidate = next(c for c in candidates if c["id"] == args.candidate)
    words = readVocabulary(candidate["vocabulary"]) if candidate.get("vocabulary") else []
    build = {"distill": buildDistilled, "append": buildAppended}[candidate["build"]]
    tokens, vectors, facts = build(candidate, words)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{candidate['id']}.npz"
    writeNpz(output, {t: i for i, t in enumerate(tokens)}, vectors, candidate["id"],
             int(vectors.shape[1]), candidate.get("license", ""), candidate.get("teacher", ""))
    tokenizer = WordPieceTokenizer(NpzStaticModel.load(output).vocabulary())
    whole = sum(1 for w in words if tokenizer.tokenize(w) == [w])
    facts.update({"tokens": len(tokens), "dimensions": int(vectors.shape[1]),
                  "extraWords": len(words), "extraWordsWhole": whole,
                  "bytes": output.stat().st_size})
    output.with_suffix(".facts.json").write_text(json.dumps(facts, indent=1) + "\n")
    print(f"Wrote {output}: {json.dumps(facts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
