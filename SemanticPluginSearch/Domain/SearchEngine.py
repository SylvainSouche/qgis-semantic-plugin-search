"""Ranking: cosine similarity between the query embedding and stored vectors.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import numpy as np

from .Entities import PluginInfo, SearchResult
from .Ports import EmbeddingEngine, PluginVectorStore


class SearchService:
    """Ranks every plugin of a store against a natural language query."""

    def __init__(self, engine: EmbeddingEngine, minScore: float = 0.02) -> None:
        self.engine = engine
        self.minScore = minScore

    def search(
        self,
        store: PluginVectorStore,
        text: str,
        limit: int = 30,
        infos: dict[int, PluginInfo] | None = None,
    ) -> list[SearchResult]:
        """Return at most limit results ordered by descending similarity.

        Plugins whose text produced no known token carry a zero vector and
        score zero, which the minScore floor filters out.
        """
        query = self.engine.embedQuery(text)
        if not np.any(query):
            return []
        scores = store.embeddings() @ query
        order = np.argsort(-scores)
        results: list[SearchResult] = []
        for index in order:
            score = float(scores[index])
            if score < self.minScore:
                break
            pluginId = store.pluginIds()[int(index)]
            info = (infos or {}).get(pluginId) or store.pluginInfo(pluginId)
            if info is None:
                continue
            results.append(SearchResult(info=info, score=score))
            if len(results) >= limit:
                break
        return results

# @impl 0f87-6ae3-6985-5a6f
