"""Search quality evaluation: the shipped ranking against keyword baselines.

Everything is measured on a pinned snapshot of the published embeddings
branch (model, per universe database and the readme cache the database was
built from), so the semantic index and the keyword baselines index exactly
the same plugin text: the text pipeline.TextPreparation embeds.

Systems compared (all see the same catalogue and the same visibility rule):

- manager:    an approximation of the QGIS plugin manager search box: the
              whole query, case insensitive, must appear as a substring of
              the name, description, author or tags; matches sorted by name.
- andfilter:  the boolean keyword search users expect from a search box:
              every keyword must start a word of the name, description,
              about, tags or author; matches sorted by name.
- bm25:       Okapi BM25 over the full embedded text (name, description,
              about, tags, readme excerpt), no stemming. The strong keyword
              baseline.
- bm25stem:   the same with a light English suffix stripper.
- lexical:    the shipped lexical boost alone (Domain.LexicalBoost).
- semantic:   the shipped static embedding cosine alone.
- hybrid:     the shipped ranking (Domain.SearchEngine.SearchService).

Metrics per query, averaged over queries: nDCG@10 with graded judgments
(2 = does the task, 1 = partly or as a side feature), Recall@20, MRR,
Success@5 (a relevant plugin in the first five), Found@10 (a plugin that
does the task, grade 2, on the first screen of ten) and Precision@10 (the
share of what is shown on that screen that is relevant: a short list of
wrong plugins scores 0, it is not credited for being short).

Each need is asked twice: as a sentence and as a keyword list. A keyword
session (keywordSession) replays how keyword search is really used: type
the first keyword, look at the first screen, add the next keyword if it
does not show a plugin that does the task, and take a keyword back out if
it empties the list. Differences between two
systems come with a paired bootstrap 95 % interval over queries.

This module is tooling: it imports the plugin Domain and Data layers but is
never shipped in the plugin package.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from SemanticPluginSearch.Data.SqliteVectorStore import SqliteVectorStore  # noqa: E402
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel  # noqa: E402
from SemanticPluginSearch.Domain.EmbeddingEngine import StaticEmbeddingEngine  # noqa: E402
from SemanticPluginSearch.Domain.Entities import PluginInfo  # noqa: E402
from SemanticPluginSearch.Domain.LexicalBoost import LexicalIndex  # noqa: E402
from SemanticPluginSearch.Domain.SearchEngine import (  # noqa: E402
    SearchService,
    visibilityPredicate,
)
from SemanticPluginSearch.Domain.WordPieceTokenizer import WordPieceTokenizer  # noqa: E402

EVALUATION_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = REPO_ROOT / "build" / "eval" / "snapshot"
# The embeddings branch commit the snapshot is extracted from (make eval).
SNAPSHOT_COMMIT = "97fc1c9592beb53d4c2e5d725898bdb34c782807"
SNAPSHOT_FILES = {
    "model": "EmbeddingModel.4f5f1043f084.npz",
    "3": ("Embeddings-3.e85e407c80cb.sqlite", "Readmes-3.json.gz"),
    "4": ("Embeddings-4.e2adea4752e9.sqlite", "Readmes-4.json.gz"),
}

CUTOFF_NDCG = 10
CUTOFF_RECALL = 20
CUTOFF_SUCCESS = 5
RANK_DEPTH = 50

SCREEN = 10

SYSTEMS = ("manager", "andfilter", "bm25", "bm25stem", "lexical", "semantic", "hybrid")
# Not shipped: reciprocal rank fusion of semantic and BM25, measured to see
# whether a keyword component stronger than the lexical boost would help.
EXPERIMENTS = ("fusion",)
RRF_K = 60


# ---------------------------------------------------------------- corpus


@dataclass
class Corpus:
    """One universe of the snapshot: store, engine and the indexed texts."""

    universe: str
    store: SqliteVectorStore
    engine: StaticEmbeddingEngine
    model: NpzStaticModel
    tokenizer: WordPieceTokenizer
    pluginIds: list[int]
    infos: list[PluginInfo]
    texts: list[str]
    visible: np.ndarray
    readmeCount: int
    byName: dict[str, list[int]] = field(default_factory=dict)

    def positionsOf(self, name: str) -> list[int]:
        return self.byName.get(name.casefold(), [])


def loadCorpus(universe: str, snapshotDir: Path = SNAPSHOT_DIR) -> Corpus:
    """Load the pinned model, database and readme cache of one universe."""
    from pipeline.TextPreparation import preparePluginText  # noqa: PLC0415
    from pipeline.PluginCatalogue import PluginRecord  # noqa: PLC0415

    databaseName, readmesName = SNAPSHOT_FILES[universe]
    model = NpzStaticModel.load(snapshotDir / SNAPSHOT_FILES["model"])
    tokenizer = WordPieceTokenizer(model.vocabulary())
    engine = StaticEmbeddingEngine(tokenizer, model)
    store = SqliteVectorStore.open(snapshotDir / databaseName)
    with gzip.open(snapshotDir / readmesName, "rt", encoding="utf-8") as handle:
        readmes = json.load(handle)["plugins"]
    pluginIds = store.pluginIds()
    infos = [store.pluginInfo(pid) for pid in pluginIds]
    texts: list[str] = []
    readmeCount = 0
    for info in infos:
        readme = (readmes.get(str(info.pluginId)) or {}).get("text") or None
        readmeCount += bool(readme)
        record = PluginRecord(
            pluginId=info.pluginId, name=info.name, version=info.version,
            description=info.description, about=info.about, tags=info.tags,
            repository="", homepage="", tracker="", downloadUrl="", iconUrl="",
            fileName="", authorName=info.author, qgisMinimum="", qgisMaximum="",
            experimental=info.experimental, deprecated=info.deprecated,
            server=info.server, downloads=0, averageVote=0.0, ratingVotes=0,
            updateDate="",
        )
        texts.append(preparePluginText(record, readme))
    keep = visibilityPredicate()
    visible = np.array([keep(info) for info in infos], dtype=bool)
    byName: dict[str, list[int]] = {}
    for position, info in enumerate(infos):
        byName.setdefault(info.name.casefold(), []).append(position)
    return Corpus(universe, store, engine, model, tokenizer, pluginIds, infos, texts,
                  visible, readmeCount, byName)


# ---------------------------------------------------------------- keyword systems

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
ENGLISH_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in into is it its my of on or "
    "that the this to was with what which who will can do does you your me want need "
    "using use some any all".split()
)


def fold(text: str) -> str:
    """Lowercase and strip accents, like the uncased BERT tokenizer does."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def keywordTokens(text: str, stem: bool = False) -> list[str]:
    words = [w for w in _WORD.findall(fold(text)) if w not in ENGLISH_STOPWORDS]
    return [lightStem(w) for w in words] if stem else words


def lightStem(word: str) -> str:
    """A deliberately small English suffix stripper (plural, -ing, -ed, -ion)."""
    if len(word) <= 4:
        return word
    for suffix, keep in (("ations", 3), ("ation", 3), ("izing", 3), ("ising", 3),
                         ("ings", 3), ("ing", 3), ("ies", 3), ("ers", 3), ("er", 3),
                         ("ed", 3), ("es", 3), ("s", 3)):
        if word.endswith(suffix) and len(word) - len(suffix) >= keep:
            if suffix == "ies":
                return word[:-3] + "y"
            if suffix == "es" and not word.endswith(("ses", "xes", "ches", "shes")):
                return word[:-1]
            return word[: -len(suffix)]
    return word


class Bm25:
    """Okapi BM25 over a list of documents."""

    def __init__(self, texts: Sequence[str], stem: bool = False,
                 k1: float = 1.2, b: float = 0.75) -> None:
        self.stem = stem
        self.k1, self.b = k1, b
        self.docs = [Counter(keywordTokens(text, stem)) for text in texts]
        self.lengths = np.array([sum(doc.values()) for doc in self.docs], dtype=np.float32)
        self.average = float(self.lengths.mean()) if len(self.docs) else 0.0
        frequency: Counter[str] = Counter()
        for doc in self.docs:
            frequency.update(doc.keys())
        count = len(self.docs)
        self.idf = {t: math.log(1 + (count - n + 0.5) / (n + 0.5)) for t, n in frequency.items()}
        self.postings: dict[str, list[int]] = {}
        for index, doc in enumerate(self.docs):
            for term in doc:
                self.postings.setdefault(term, []).append(index)

    def scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.docs), dtype=np.float32)
        norm = self.k1 * (1 - self.b + self.b * self.lengths / max(self.average, 1e-9))
        for term in dict.fromkeys(keywordTokens(query, self.stem)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for index in self.postings[term]:
                tf = self.docs[index][term]
                scores[index] += idf * tf * (self.k1 + 1) / (tf + norm[index])
        return scores


def managerRanking(corpus: Corpus, query: str) -> list[int]:
    """Approximation of the plugin manager filter: phrase substring, by name."""
    needle = query.strip().casefold()
    if not needle:
        return []
    hits = []
    for position, info in enumerate(corpus.infos):
        haystacks = (info.name, info.description, info.author, " ".join(info.tags))
        if any(needle in (text or "").casefold() for text in haystacks):
            hits.append(position)
    return sorted(hits, key=lambda p: corpus.infos[p].name.casefold())


class AndFilter:
    """Every keyword must start a word of the plugin's visible fields."""

    def __init__(self, infos: Sequence[PluginInfo]) -> None:
        self.texts = [" " + " ".join(_WORD.findall(fold(" ".join(
            (info.name, info.description, info.about or "", " ".join(info.tags),
             info.author or ""))))) for info in infos]
        self.names = [info.name.casefold() for info in infos]

    def matches(self, keywords: Sequence[str]) -> list[int]:
        needles = [" " + " ".join(_WORD.findall(fold(k))) for k in keywords]
        needles = [n for n in needles if n.strip()]
        if not needles:
            return []
        hits = [i for i, text in enumerate(self.texts) if all(n in text for n in needles)]
        return sorted(hits, key=lambda i: self.names[i])


# ---------------------------------------------------------------- systems


class EncodedVectors:
    """Document vectors and a query encoder from any embedding model.

    Rows of documents are L2 normalised; encodeQuery returns one vector of
    the same width, or None for an all-zero one. Used by the embedding
    benchmark to run the semantic and hybrid systems on another model.
    """

    def __init__(self, documents: np.ndarray, encodeQuery: Callable[[str], np.ndarray]) -> None:
        documents = np.asarray(documents, dtype=np.float32)
        norms = np.linalg.norm(documents, axis=1, keepdims=True)
        self.documents = documents / np.where(norms > 0, norms, 1.0)
        self._encode = encodeQuery
        self._cache: dict[str, np.ndarray | None] = {}

    def query(self, text: str) -> np.ndarray | None:
        if text not in self._cache:
            vector = np.asarray(self._encode(text), dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(vector))
            self._cache[text] = vector / norm if norm > 0 else None
        return self._cache[text]


HYBRID_MIN_SCORE = 0.02  # SearchService's default floor


class Systems:
    """Every compared ranking over one corpus, returning store positions.

    With vectors, the semantic, hybrid and fusion systems use those
    instead of the shipped model; the keyword systems are unchanged.
    """

    def __init__(self, corpus: Corpus, vectors: EncodedVectors | None = None) -> None:
        self.corpus = corpus
        self.vectors = vectors
        self.bm25 = Bm25(corpus.texts)
        self.bm25stem = Bm25(corpus.texts, stem=True)
        self.lexical = LexicalIndex(corpus.infos)
        self.andFilter = AndFilter(corpus.infos)
        self.service = SearchService(corpus.engine)
        self._position = {pid: i for i, pid in enumerate(corpus.pluginIds)}

    def rankKeywords(self, system: str, keywords: Sequence[str],
                     depth: int = RANK_DEPTH) -> list[int]:
        """A keyword list: each keyword as typed, or the list joined by spaces."""
        if system == "andfilter":
            corpus = self.corpus
            return [p for p in self.andFilter.matches(keywords) if corpus.visible[p]][:depth]
        return self.rank(system, " ".join(keywords), depth)

    def rank(self, system: str, query: str, depth: int = RANK_DEPTH) -> list[int]:
        corpus = self.corpus
        if system == "andfilter":
            # A sentence typed into a boolean search box: every content word.
            return self.rankKeywords(system, keywordTokens(query), depth)
        if system == "manager":
            return [p for p in managerRanking(corpus, query) if corpus.visible[p]][:depth]
        if system == "hybrid" and self.vectors is not None:
            vector = self.vectors.query(query)
            semantic = (self.vectors.documents @ vector if vector is not None
                        else np.zeros(len(corpus.infos), np.float32))
            scores = semantic + self.lexical.boosts(query)
            masked = np.where(corpus.visible & (scores >= HYBRID_MIN_SCORE), scores, -np.inf)
            order = np.argsort(-masked, kind="stable")[:depth]
            return [int(i) for i in order if np.isfinite(masked[i])]
        if system == "hybrid":
            results = self.service.search(corpus.store, query, limit=depth,
                                          predicate=visibilityPredicate())
            return [self._position[r.info.pluginId] for r in results]
        if system == "fusion":
            fused: dict[int, float] = {}
            for part in ("semantic", "bm25"):
                for rank, position in enumerate(self.rank(part, query, depth=200)):
                    fused[position] = fused.get(position, 0.0) + 1.0 / (RRF_K + rank + 1)
            return sorted(fused, key=lambda p: -fused[p])[:depth]
        if system == "bm25":
            scores = self.bm25.scores(query)
        elif system == "bm25stem":
            scores = self.bm25stem.scores(query)
        elif system == "lexical":
            scores = self.lexical.boosts(query)
        elif system == "semantic" and self.vectors is not None:
            vector = self.vectors.query(query)
            if vector is None:
                return []
            scores = self.vectors.documents @ vector
        elif system == "semantic":
            vector = corpus.engine.embedQuery(query)
            scores = corpus.store.embeddings() @ vector if np.any(vector) else None
            if scores is None:
                return []
        else:
            raise ValueError(f"unknown system {system!r}")
        return _topPositive(scores, corpus.visible, depth)


def _topPositive(scores: np.ndarray, visible: np.ndarray, depth: int) -> list[int]:
    masked = np.where(visible, scores, -np.inf)
    order = np.argsort(-masked, kind="stable")[:depth]
    return [int(i) for i in order if masked[i] > 0]


# ---------------------------------------------------------------- metrics


def dcg(gains: Sequence[float]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def queryMetrics(ranked: Sequence[str], judgments: dict[str, int]) -> dict[str, float]:
    """Metrics of one ranked list of plugin names against graded judgments."""
    relevant = {name for name, grade in judgments.items() if grade > 0}
    gains = [judgments.get(name, 0) for name in ranked]
    ideal = sorted((g for g in judgments.values() if g > 0), reverse=True)
    idealDcg = dcg(ideal[:CUTOFF_NDCG])
    firstHit = next((i for i, g in enumerate(gains) if g > 0), None)
    found = {name for name in ranked[:CUTOFF_RECALL] if name in relevant}
    screen = gains[:SCREEN]
    return {
        "found@10": 1.0 if any(g >= 2 for g in screen) else 0.0,
        "precision@10": sum(1 for g in screen if g > 0) / len(screen) if screen else 0.0,
        "ndcg@10": dcg(gains[:CUTOFF_NDCG]) / idealDcg if idealDcg else 0.0,
        "recall@20": len(found) / len(relevant) if relevant else 0.0,
        "mrr": 1.0 / (firstHit + 1) if firstHit is not None else 0.0,
        "success@5": 1.0 if firstHit is not None and firstHit < CUTOFF_SUCCESS else 0.0,
    }


METRICS = ("ndcg@10", "found@10", "precision@10", "recall@20", "mrr", "success@5")


# ---------------------------------------------------------------- keyword sessions


@dataclass
class SessionStep:
    keywords: list[str]
    shown: list[str]
    size: int
    kept: bool


@dataclass
class SessionOutcome:
    """Where an adaptive keyword session stopped and what the user saw then."""

    steps: list[SessionStep]
    found: bool
    keywordsTyped: int
    metrics: dict[str, float]

    @property
    def final(self) -> SessionStep:
        kept = [step for step in self.steps if step.kept]
        return kept[-1] if kept else self.steps[-1]


def keywordSession(rank: Callable[[list[str]], list[str]], keywords: Sequence[str],
                   judgments: dict[str, int]) -> SessionOutcome:
    """Replay a keyword search session over one ranking function.

    The user types the first keyword and reads the first screen. If it
    shows a plugin that does the task (grade 2) they stop. Otherwise they add
    the next keyword. A keyword that empties the list is taken back out
    (even the first one) and the session continues with the next one. When
    the keywords run out, the session ends on the last non empty list.
    rank maps a keyword list to the ranked plugin names.
    """
    current: list[str] = []
    steps: list[SessionStep] = []
    for keyword in keywords:
        attempt = [*current, keyword]
        names = rank(attempt)
        kept = bool(names)
        steps.append(SessionStep(attempt, names[:SCREEN], len(names), kept))
        if kept:
            current = attempt
            if any(judgments.get(n, 0) >= 2 for n in names[:SCREEN]):
                break
    outcome = SessionOutcome(steps, False, len(steps), {})
    outcome.metrics = queryMetrics(rank(outcome.final.keywords), judgments)
    outcome.found = outcome.metrics["found@10"] > 0
    return outcome


def pairedBootstrap(a: Sequence[float], b: Sequence[float], rounds: int = 10000,
                    seed: int = 20261112) -> tuple[float, float, float]:
    """Mean of b - a with a 95 % percentile bootstrap interval over queries."""
    diff = np.asarray(b, dtype=np.float64) - np.asarray(a, dtype=np.float64)
    if diff.size == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, diff.size, size=(rounds, diff.size))
    means = diff[samples].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


# ---------------------------------------------------------------- tokenizer diagnostics


def tokenCoverage(corpus: Corpus, text: str) -> dict[str, float]:
    """How the English WordPiece vocabulary sees a query.

    unk: share of words that become [UNK] (silently dropped by the engine);
    pieces: average WordPiece pieces per word (1 = whole word known).
    """
    words = [w for w in corpus.tokenizer._basicChunks(text)
             if not all(corpus.tokenizer._isPunctuation(c) for c in w)]
    if not words:
        return {"unk": 0.0, "pieces": 0.0}
    unk = pieces = 0
    for word in words:
        tokens = corpus.tokenizer.tokenize(word)
        if not tokens or tokens == [corpus.tokenizer.unkToken]:
            unk += 1
        pieces += max(len(tokens), 1)
    return {"unk": unk / len(words), "pieces": pieces / len(words)}


# ---------------------------------------------------------------- language of a text

_STOPWORDS_BY_LANGUAGE = {
    "en": "the and of to is for with this that from are by be it on as an you can",
    "fr": "le la les des du de et est pour une un dans sur avec qui par au aux ce",
    "es": "el la los las del de y es para una un en con que por se al como",
    "pt": "o a os as do da dos das de e é para uma um em com que por se ao no na",
    "de": "der die das und ist für mit ein eine von zu den im auf werden nicht",
    "it": "il lo la gli le di del della e è per una un con che in da sono",
}
_STOPWORD_SETS = {lang: frozenset(words.split()) for lang, words in _STOPWORDS_BY_LANGUAGE.items()}


def textLanguage(text: str) -> str:
    """A coarse language guess: script first, then the most frequent stopwords.

    Returns en, fr, es, pt, de, it, ru, cjk, ko or '?'. Good enough to tell
    which language dominates a plugin's text, not to classify a sentence.
    """
    if sum(1 for ch in text if "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿") > 5:
        return "cjk"
    if sum(1 for ch in text if "가" <= ch <= "힯") > 5:
        return "ko"
    if sum(1 for ch in text if "Ѐ" <= ch <= "ӿ") > 20:
        return "ru"
    words = re.findall(r"[^\W\d_]+", text.lower())
    counts = {lang: sum(word in stop for word in words) for lang, stop in _STOPWORD_SETS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] >= 2 else "?"


# ---------------------------------------------------------------- data files


def loadJson(name: str) -> dict:
    return json.loads((EVALUATION_DIR / name).read_text(encoding="utf-8"))


def namesOf(corpus: Corpus, positions: Sequence[int]) -> list[str]:
    return [corpus.infos[p].name for p in positions]


RankFunction = Callable[[str, str], list[int]]
