"""Lexical boost for hybrid ranking.

Static embeddings rank by meaning, but they can miss the obvious: typing a
plugin's exact name ("quickwkt", "qgis2web") should put that plugin first,
and a query word that literally appears in a plugin name or tags is strong
evidence. The boost adds a small, bounded amount to the cosine similarity
for those literal matches; it never removes a semantic hit.

Weights (added to the cosine score, which typically sits between 0.1 and 0.7):

- exact name: the whole query equals the plugin name, ignoring case, spaces
  and punctuation: +EXACT_NAME_BOOST;
- name words: fraction of query terms found in the name, times NAME_WEIGHT;
- tags: fraction of query terms found in the tags, times TAG_WEIGHT;
- description: fraction found in the description, times DESCRIPTION_WEIGHT.

A query term matches a word when they are equal or, for words of at least
PREFIX_MIN characters, when one is a prefix of the other and covers at least
PREFIX_RATIO of it (digitize matches digitizer, quickwkt does not match
quick). Terms shorter than MIN_TERM characters and common English stopwords
are ignored.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np

from .Entities import PluginInfo

EXACT_NAME_BOOST = 0.30
NAME_WEIGHT = 0.20
TAG_WEIGHT = 0.10
DESCRIPTION_WEIGHT = 0.05
MIN_TERM = 3
PREFIX_MIN = 4
PREFIX_RATIO = 0.7

STOPWORDS = frozenset(
    "the and for from with into onto that this these those are was were has have "
    "can how what which who will would should could any all some each per via "
    "plugin plugins qgis tool tools".split()
)

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_WORD = re.compile(r"[^0-9a-z]+")


def terms(text: str) -> list[str]:
    """Lowercase words of text, camelCase split, stopwords and short words removed."""
    spaced = _CAMEL.sub(" ", text or "")
    words = _NON_WORD.split(spaced.lower())
    return [word for word in words if len(word) >= MIN_TERM and word not in STOPWORDS]


def compactName(text: str) -> str:
    """The name reduced to letters and digits, for exact name comparison."""
    return _NON_WORD.sub("", (text or "").lower())


def _matchingWords(term: str, vocabulary: Iterable[str]) -> list[str]:
    exact = [term] if term in vocabulary else []
    if len(term) < PREFIX_MIN:
        return exact
    return exact + [
        word
        for word in vocabulary
        if word != term
        and len(word) >= PREFIX_MIN
        and (word.startswith(term) or term.startswith(word))
        and min(len(word), len(term)) >= PREFIX_RATIO * max(len(word), len(term))
    ]


class LexicalIndex:
    """Inverted index of plugin name, tag and description words.

    Built once per store; a query costs one scan of the vocabulary per query
    term (for prefix matches), independent of the number of plugins.
    """

    def __init__(self, infos: Sequence[PluginInfo | None]) -> None:
        self.size = len(infos)
        self._fields: list[tuple[float, dict[str, set[int]]]] = [
            (NAME_WEIGHT, {}),
            (TAG_WEIGHT, {}),
            (DESCRIPTION_WEIGHT, {}),
        ]
        self._compact: dict[str, list[int]] = {}
        for index, info in enumerate(infos):
            if info is None:
                continue
            texts = (info.name, " ".join(info.tags), info.description)
            for (_weight, postings), text in zip(self._fields, texts):
                for word in terms(text):
                    postings.setdefault(word, set()).add(index)
            compact = compactName(info.name)
            if compact:
                self._compact.setdefault(compact, []).append(index)

    def boosts(self, query: str) -> np.ndarray:
        """The boost of every plugin for the query, aligned with store order."""
        boost = np.zeros(self.size, dtype=np.float32)
        for index in self._compact.get(compactName(query), []):
            boost[index] += EXACT_NAME_BOOST
        queryTerms = list(dict.fromkeys(terms(query)))
        if not queryTerms:
            return boost
        share = 1.0 / len(queryTerms)
        for weight, postings in self._fields:
            for term in queryTerms:
                hits: set[int] = set()
                for word in _matchingWords(term, postings):
                    hits |= postings[word]
                if hits:
                    boost[list(hits)] += weight * share
        return boost
# @impl 4be9-6ae3-f123-5b3c
