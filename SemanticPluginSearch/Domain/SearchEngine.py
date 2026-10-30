"""Hybrid ranking: cosine similarity between the query embedding and the
stored vectors, plus a bounded lexical boost for literal matches in plugin
names, tags and descriptions (Domain.LexicalBoost).

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .Entities import PluginInfo, SearchResult
from .LexicalBoost import LexicalIndex
from .Ports import EmbeddingEngine, PluginVectorStore


def visibilityPredicate(
    includeExperimental: bool = False,
    includeDeprecated: bool = False,
) -> Callable[[PluginInfo], bool]:
    """The visibility rule as a predicate, applied before the result cut."""

    def keep(info: PluginInfo) -> bool:
        return (includeExperimental or not info.experimental) and (
            includeDeprecated or not info.deprecated
        )

    return keep


def filterResults(
    results: list[SearchResult],
    includeExperimental: bool = False,
    includeDeprecated: bool = False,
) -> list[SearchResult]:
    """Keep standard plugins; add experimental and deprecated when allowed.

    A plugin flagged both experimental and deprecated needs both toggles.
    """
    keep = visibilityPredicate(includeExperimental, includeDeprecated)
    return [result for result in results if keep(result.info)]


class SearchService:
    """Ranks every plugin of a store against a natural language query."""

    def __init__(self, engine: EmbeddingEngine, minScore: float = 0.02) -> None:
        self.engine = engine
        self.minScore = minScore
        self._lexicalKey: tuple[int, str] | None = None
        self._lexical: LexicalIndex | None = None

    def _lexicalIndexFor(self, store: PluginVectorStore) -> LexicalIndex:
        """One lexical index per store, rebuilt when the store changes."""
        key = (id(store), store.buildStamp())
        if self._lexical is None or self._lexicalKey != key:
            self._lexical = LexicalIndex([store.pluginInfo(pid) for pid in store.pluginIds()])
            self._lexicalKey = key
        return self._lexical

    def search(
        self,
        store: PluginVectorStore,
        text: str,
        limit: int = 30,
        infos: dict[int, PluginInfo] | None = None,
        predicate: Callable[[PluginInfo], bool] | None = None,
    ) -> list[SearchResult]:
        """Return at most limit results ordered by descending hybrid score.

        The predicate filters BEFORE the limit so hiding categories never
        shrinks the visible result count. Plugins whose text produced no
        known token carry a zero vector and score zero, which the minScore
        floor filters out unless a literal match lifts them.
        """
        query = self.engine.embedQuery(text)
        matrix = store.embeddings()
        # A dimension mismatch means "no results", never a crash.
        if query.shape[0] != matrix.shape[1]:
            return []
        # A zero query (unknown vocabulary, model still downloading) has no
        # semantic part; literal name matches can still answer it.
        semantic = matrix @ query if np.any(query) else np.zeros(matrix.shape[0], np.float32)
        scores = semantic + self._lexicalIndexFor(store).boosts(text)
        order = np.argsort(-scores, kind="stable")
        pluginIds = store.pluginIds()
        results: list[SearchResult] = []
        for index in order:
            score = float(scores[index])
            if score < self.minScore:
                break
            pluginId = pluginIds[int(index)]
            info = (infos or {}).get(pluginId) or store.pluginInfo(pluginId)
            if info is None or (predicate is not None and not predicate(info)):
                continue
            results.append(
                SearchResult(info=info, score=min(score, 1.0), semantic=float(semantic[index]))
            )
            if len(results) >= limit:
                break
        return results

# @impl 4be9-6ae3-f123-5b3c

# @impl 0f87-6ae3-a1e6-cf4c
