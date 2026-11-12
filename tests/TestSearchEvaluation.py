"""The evaluation's own arithmetic: metrics, bootstrap, keyword baselines.

These run without the embeddings snapshot; `make eval` runs the evaluation.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from SemanticPluginSearch.Domain.Entities import PluginInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from SearchEvaluation import (  # noqa: E402
    EVALUATION_DIR,
    AndFilter,
    Bm25,
    EncodedVectors,
    keywordSession,
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
    assert set(metrics.values()) == {0.0}


def testPrecisionCountsOnlyWhatIsShownAndFoundNeedsAFullMatch():
    metrics = queryMetrics(["x", "a", "b"], {"a": 1, "b": 1})
    assert metrics["precision@10"] == pytest.approx(2 / 3)
    assert metrics["found@10"] == 0.0
    metrics = queryMetrics(["x", "y"], {"a": 2})
    assert metrics["precision@10"] == 0.0
    names = [f"n{i}" for i in range(10)] + ["a"]
    assert queryMetrics(names, {"a": 2})["found@10"] == 0.0
    assert queryMetrics(names[1:], {"a": 2})["found@10"] == 1.0


def _info(name, description="", tags=()):
    return PluginInfo(pluginId=len(name), name=name, description=description, tags=tuple(tags))


def testAndFilterNeedsEveryKeywordAtAWordStartAndSortsByName():
    infos = [_info("Zeta contours", "contour lines from a DEM"),
             _info("Alpha", "Contour generator", ["dem"]),
             _info("Decontour", "removes outlines from DEMs"),
             _info("Web map", "export a web map")]
    andFilter = AndFilter(infos)
    assert andFilter.matches(["contour", "dem"]) == [1, 0]
    assert andFilter.matches(["web map"]) == [3]
    assert andFilter.matches(["map web"]) == []
    assert andFilter.matches([]) == []


def testKeywordSessionStopsOnTheFirstScreenThatShowsTheTask():
    lists = {("a",): ["x", "y"], ("a", "b"): ["x", "good"], ("a", "b", "c"): ["good"]}
    outcome = keywordSession(lambda k: lists.get(tuple(k), []), ["a", "b", "c"], {"good": 2})
    assert outcome.found and outcome.keywordsTyped == 2
    assert outcome.final.keywords == ["a", "b"]
    assert outcome.metrics["precision@10"] == 0.5


def testKeywordSessionDropsAKeywordThatEmptiesTheList():
    lists = {("a",): ["x"], ("a", "c"): ["good"]}
    outcome = keywordSession(lambda k: lists.get(tuple(k), []), ["a", "b", "c"], {"good": 2})
    assert [s.kept for s in outcome.steps] == [True, False, True]
    assert outcome.found and outcome.final.keywords == ["a", "c"]
    outcome = keywordSession(lambda k: lists.get(tuple(k), []), ["a", "b"], {"good": 2})
    assert not outcome.found and outcome.final.keywords == ["a"]


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
        for keywords in (query["generated"]["keywords"], query["authorKeywords"]):
            assert 1 <= len(keywords) <= 4 and all(keywords), query["id"]
        assert query["generated"]["sentence"], query["id"]


def testEncodedVectorsNormaliseAndCacheQueries():
    calls = []

    def encode(text):
        calls.append(text)
        return [3.0, 4.0] if text else [0.0, 0.0]

    vectors = EncodedVectors([[2.0, 0.0], [0.0, 0.0]], encode)
    assert vectors.documents[0].tolist() == [1.0, 0.0]
    assert vectors.documents[1].tolist() == [0.0, 0.0]
    assert vectors.query("x").tolist() == pytest.approx([0.6, 0.8])
    vectors.query("x")
    assert calls == ["x"]
    assert vectors.query("") is None


def testCandidatesAreWellFormed():
    candidates = json.loads((EVALUATION_DIR / "Candidates.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in candidates["candidates"]]
    assert len(ids) == len(set(ids)) and "shipped" in ids
    for candidate in candidates["candidates"]:
        assert candidate["kind"] in {"shipped", "model2vec", "sentence-transformers"}
        assert candidate["class"] in {"static", "transformer"}
        assert candidate["kind"] == "shipped" or candidate["model"]
