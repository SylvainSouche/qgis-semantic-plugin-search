"""Merge benchmark results into one comparison table.

    python evaluation/BenchmarkReport.py build/benchmark > report.md

Reads every <candidate>.json written by RunBenchmark.py in the folder and
prints a Markdown report: English quality on the QGIS 3 catalogue,
cross-language quality, size and speed. A value marked with * still has
unjudged plugins on its first screens: it is the judged value, and the
optimistic bound (unjudged counted as partly relevant) follows in brackets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EUROPEAN = ("fr", "de", "es", "pt", "it")
OTHER = ("ru", "zh", "ja")


def cell(entry: dict, key: str = "ndcg@10") -> str:
    value = f"{entry[key]:.3f}"
    if entry.get("judged@10", 1.0) < 0.995 and "upper" in entry and key == "ndcg@10":
        return f"{value}* ({entry['upper']:.3f})"
    return value


def capture(universe: dict) -> float:
    return sum(universe["cross"][lang]["sameLanguageTop10"] for lang in EUROPEAN) / len(EUROPEAN)


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])


def report(folder: Path) -> str:
    results = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(folder.glob("*.json")) if not p.name.endswith(".unjudged.json")]
    order = [c["id"] for c in json.loads(
        (Path(__file__).resolve().parent / "Candidates.json").read_text())["candidates"]]
    results.sort(key=lambda r: order.index(r["candidate"]["id"])
                 if r["candidate"]["id"] in order else len(order))
    pending = {p.name[:-len(".unjudged.json")]: len(json.loads(p.read_text(encoding="utf-8")))
               for p in folder.glob("*.unjudged.json")}
    english, cross, facts = [], [], []
    for r in results:
        c, u = r["candidate"], r["universes"]["3"]
        e = u["english"]
        english.append([c["id"], c["class"],
                        cell(e["hybrid/sentence"]), cell(e["hybrid/keywords"]),
                        cell(e["semantic/sentence"]),
                        f"{e['hybrid/sentence']['precision@10']:.3f}",
                        f"{e['hybrid/sentence']['found@10']:.0%}",
                        f"{u['hybridSession']['found']:.0%}",
                        f"{e['hybrid/sentence']['judged@10']:.0%}"])
        if "cross" in u:
            en = e["hybrid/author sentence"]["ndcg@10"]
            kept = [u["cross"][lang]["ndcg@10"] / en if en else 0.0 for lang in EUROPEAN]
            cross.append([c["id"],
                          f"{sum(kept) / len(kept):.0%}",
                          *(cell(u["cross"][lang]) for lang in OTHER),
                          f"{capture(u):.0%}",
                          cell(u["native"]), cell(u["nativeInEnglish"])])
        f = r.get("facts", {})
        size = f.get("parameters")
        facts.append([c["id"], c.get("license", "?"), str(f.get("dimensions", "?")),
                      f"{size / 1e6:.1f} M" if size else "?",
                      f"{f.get('documentSeconds', '?')} s", f"{f.get('queryMilliseconds', '?')} ms",
                      str(pending.get(c["id"], "?")), (f.get("revision") or "?")[:12]])
    md = ["# Embedding model benchmark", "",
          f"Snapshot `{results[0]['snapshot'][:12]}`. QGIS 3 catalogue, the 40 needs of "
          "evaluation/Queries.json, judgments of evaluation/Judgments.json. Values with * have "
          "unjudged plugins on their first screens: judged value, optimistic bound in "
          "brackets.", "",
          "## English", "",
          table(["model", "class", "hybrid sentence nDCG@10", "hybrid keywords nDCG@10",
                 "semantic only, sentence", "precision@10", "found@10",
                 "keyword session found", "judged@10"], english), ""]
    if cross:
        md += ["## Across languages (author sentences, hybrid)", "",
               "`EU kept`: mean share of the English nDCG@10 kept in French, German, Spanish, "
               "Portuguese and Italian. `same-lang`: share of the top ten written in the query "
               "language (lower is better: it measures language capture).", "",
               table(["model", "EU kept", "ru", "zh", "ja", "same-lang", "native needs, native",
                      "native needs, English"], cross), ""]
    md += ["## Size and speed", "",
           "Parameters of the embedding table or network; document time embeds the whole "
           "catalogue on the CI runner's CPU; query time is per query.", "",
           table(["model", "license", "dim", "parameters", "catalogue embedding", "per query",
                  "unjudged pairs", "model revision"], facts), ""]
    return "\n".join(md)


if __name__ == "__main__":
    print(report(Path(sys.argv[1] if len(sys.argv) > 1 else "build/benchmark")))
