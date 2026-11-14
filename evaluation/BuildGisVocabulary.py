"""Build evaluation/GisVocabulary.tsv: GIS words the model's vocabulary splits.

    python evaluation/BuildGisVocabulary.py /path/to/gis-glossary/published

Reads the English terms of the gis-glossary project's published term lists
(ISO/TC 211 MLGT, IATE GIS terms, QGIS interface labels, QGIS manual
headings, INSPIRE regulation names, OpenStreetMap tagging schema labels,
GEMET, CORINE land cover classes; see GisVocabulary.ATTRIBUTION.md), splits
them into words, and
keeps the words of four letters or more that the shipped model's WordPiece
vocabulary cannot represent as one token (it cuts them into pieces such as
con + ##tour). Left out: the broad Snorre termbase (every standards field,
not GIS), the general Icelandic dictionaries, and Kartverket INT 1 (no reuse
terms).

The words are chosen from the glossary only, never from the evaluation's
queries. plugin_docs counts the snapshot plugin texts (QGIS 3 and 4) that
contain the word, for information.
"""
from __future__ import annotations

import collections
import csv
import lzma
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from SearchEvaluation import ENGLISH_STOPWORDS, EVALUATION_DIR, loadCorpus  # noqa: E402

WORD = re.compile(r"[a-z][a-z0-9]+")
MIN_LENGTH = 4
OUTPUT = EVALUATION_DIR / "GisVocabulary.tsv"


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def glossaryTerms(published: Path) -> dict[str, set[str]]:
    csv.field_size_limit(10**8)
    terms: dict[str, set[str]] = collections.defaultdict(set)
    with (published / "iso-mlgt/mlgt_terms.csv").open(encoding="utf-8") as stream:
        terms["iso-mlgt"] = {r["term"] for r in csv.DictReader(stream) if r["language"] == "en"}
    with (published / "iate/iate_gis_terms.csv").open(encoding="utf-8") as stream:
        terms["iate"] = {r["term"] for r in csv.DictReader(stream) if r["language"] == "en"}
    with lzma.open(published / "qgis-gui/qgis_gui_labels.csv.xz", "rt", encoding="utf-8") as stream:
        terms["qgis-gui"] = {r["source_text"] for r in csv.DictReader(stream)}
    with (published / "qgis-manual-headings/qgis_manual_headings.tsv").open(encoding="utf-8") as s:
        terms["qgis-manual"] = {r["en"] for r in csv.DictReader(s, delimiter="\t") if r["en"]}
    with (published / "inspire-regulation/inspire_reg_en.csv").open(encoding="utf-8") as stream:
        terms["inspire"] = {r["label"] for r in csv.DictReader(stream) if r["language"] == "en"}
    with lzma.open(published / "osm-tagging-schema/osm_terms.csv.xz", "rt", encoding="utf-8") as s:
        terms["osm"] = {r["text"] for r in csv.DictReader(s) if r["language"] == "en"}
    with lzma.open(published / "gemet/gemet_labels.csv.xz", "rt", encoding="utf-8") as s:
        terms["gemet"] = {r["label"] for r in csv.DictReader(s) if r["language"] == "en"}
    with (published / "corine-land-cover-no/clc_nomenclature_nb_en.csv").open(encoding="utf-8") as s:
        terms["corine"] = {r["en"] for r in csv.DictReader(s) if r["en"]}
    return terms


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__)
        return 2
    terms = glossaryTerms(Path(args[0]))
    corpora = [loadCorpus("3"), loadCorpus("4")]
    tokenizer = corpora[0].tokenizer
    documents: collections.Counter[str] = collections.Counter()
    for text in {t for corpus in corpora for t in corpus.texts}:
        documents.update(set(WORD.findall(fold(text))))
    sources: dict[str, set[str]] = collections.defaultdict(set)
    for source, texts in terms.items():
        for text in texts:
            for word in WORD.findall(fold(text)):
                if len(word) >= MIN_LENGTH and word not in ENGLISH_STOPWORDS:
                    sources[word].add(source)
    rows = []
    for word, found in sources.items():
        pieces = tokenizer.tokenize(word)
        if len(pieces) >= 2 and tokenizer.unkToken not in pieces:
            rows.append((word, ",".join(sorted(found)), documents[word], " ".join(pieces)))
    rows.sort(key=lambda row: (-row[2], row[0]))
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["word", "sources", "plugin_docs", "pieces_today"])
        writer.writerows(rows)
    print(f"Wrote {OUTPUT}: {len(rows)} words, {sum(1 for r in rows if r[2])} in plugin texts")
    print("words per source:", {source: sum(1 for r in rows if source in r[1].split(","))
                                for source in terms})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
