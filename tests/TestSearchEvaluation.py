"""The evaluation's own arithmetic: metrics, bootstrap, keyword baselines.

These run without the embeddings snapshot; `make eval` runs the evaluation.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from SearchEvaluation import (  # noqa: E402
    EVALUATION_DIR,
    Bm25,
    keywordTokens,
    lightStem,
    pairedBootstrap,
    queryMetrics,
    textLanguage,
)


def testPerfectRankingScoresOne():
    metrics = queryMetrics(["a", "b"], {"a": 2, "b": 1})
    assert metrics["ndcg@10"] == pytest.approx(1.0)
    assert metrics["recall@20"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["success@5"] == 1.0


def testGradedNdcgPrefersTheBetterPluginFirst():
    judgments = {"a": 2, "b": 1}
    assert queryMetrics(["b", "a"], judgments)["ndcg@10"] < 1.0
    expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
    assert queryMetrics(["b", "a"], judgments)["ndcg@10"] == pytest.approx(expected)


def testUnjudgedResultsCountAsNotRelevant():
    metrics = queryMetrics(["x", "y", "z", "q", "r", "a"], {"a": 1})
    assert metrics["mrr"] == pytest.approx(1 / 6)
    assert metrics["success@5"] == 0.0
    assert metrics["recall@20"] == 1.0


def testEmptyRankingScoresZero():
    metrics = queryMetrics([], {"a": 2})
    assert metrics == {"ndcg@10": 0.0, "recall@20": 0.0, "mrr": 0.0, "success@5": 0.0}


def testPairedBootstrapIsCenteredOnTheMeanDifference():
    mean, low, high = pairedBootstrap([0.1, 0.2, 0.3, 0.4], [0.3, 0.4, 0.5, 0.6])
    assert mean == pytest.approx(0.2)
    assert low == pytest.approx(0.2) and high == pytest.approx(0.2)
    mean, low, high = pairedBootstrap([0.0, 1.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0])
    assert low < mean < high


def testKeywordTokensFoldAccentsAndDropStopwords():
    assert keywordTokens("Créer des courbes de niveau à partir d'un MNT") == [
        "creer", "des", "courbes", "de", "niveau", "partir", "d", "un", "mnt"]
    assert keywordTokens("the contour lines of a DEM") == ["contour", "lines", "dem"]


def testLightStemmerMergesSimpleInflections():
    assert lightStem("contours") == lightStem("contour") == "contour"
    assert lightStem("lines") == lightStem("line") == "line"
    assert lightStem("boundaries") == "boundary"
    assert lightStem("routing") == "rout"
    assert lightStem("dem") == "dem"


def testBm25RanksTheMatchingDocumentFirst():
    index = Bm25(["contour lines from elevation", "geocode addresses", "print layouts"])
    scores = index.scores("contour lines")
    assert scores.argmax() == 0
    assert scores[1] == 0 and scores[2] == 0


def testTextLanguageRecognisesTheMainLanguages():
    assert textLanguage("This plugin creates the contour lines for a DEM and it is fast") == "en"
    assert textLanguage("Ce plugin permet de créer les courbes de niveau pour une zone") == "fr"
    assert textLanguage("Este complemento calcula el índice con las imágenes del satélite") == "es"
    assert textLanguage("国土地理院の地図タイルを表示する") == "cjk"
    assert textLanguage("") == "?"


def testJudgmentsCoverEveryQuery():
    queries = json.loads((EVALUATION_DIR / "Queries.json").read_text(encoding="utf-8"))
    judgments = json.loads((EVALUATION_DIR / "Judgments.json").read_text(encoding="utf-8"))
    ids = [q["id"] for q in queries["queries"]] + [q["id"] for q in queries["native"]]
    assert sorted(judgments["judgments"]) == sorted(ids)
    for qid in ids:
        grades = judgments["judgments"][qid].values()
        assert any(g > 0 for g in grades), qid
        assert set(grades) <= {1, 2}, qid
    for query in queries["queries"]:
        assert all(query.get(lang) for lang in queries["languages"]), query["id"]
