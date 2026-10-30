"""Sanity gate before publishing a new embeddings release.

A bad build (partial catalogue, fetch outage) must never replace good
stored embeddings. The gate compares each universe plugin count against the
stored index and fails when the count is zero or outside the tolerance. An
empty store always passes (first build). Used by pipeline/StoreEmbeddings.py.
"""
from __future__ import annotations


TOLERANCE = 0.10


def checkGates(newIndex: dict, previousCounts: dict[str, int] | None) -> list[str]:
    """Return the list of gate violations (empty means publish)."""
    violations: list[str] = []
    for universe, release in (newIndex.get("universes") or {}).items():
        count = int(release.get("plugin_count", 0))
        if count <= 0:
            violations.append(f"universe {universe}: plugin count is {count}")
            continue
        if previousCounts is None:
            continue
        previous = int(previousCounts.get(universe, 0))
        if previous <= 0:
            continue
        if abs(count - previous) > TOLERANCE * previous:
            violations.append(
                f"universe {universe}: plugin count {count} deviates more than "
                f"{TOLERANCE:.0%} from the previous build ({previous})"
            )
    return violations
