"""Sanity gate before publishing a new embeddings release.

A bad build (partial catalogue, fetch outage) must never replace a good
release. The gate compares each universe plugin count against the previously
published index and fails when the count is missing, zero, or outside the
tolerance. A missing previous release always passes (first publish).

Usage:
    python pipeline/PublishGate.py \
        --index build/index.json \
        --previous-url https://github.com/OWNER/REPO/releases/download/embeddings/index.json
"""

import json
import sys
from pathlib import Path

TOLERANCE = 0.10


def loadPreviousCounts(previousUrl: str) -> dict[str, int] | None:
    """Fetch the previous index counts; None when there is nothing to compare."""
    try:
        from SemanticPluginSearch.Data.AssetGateways import fetchUrl

        document = json.loads(fetchUrl(previousUrl))
    except Exception:  # noqa: BLE001 - no previous release or unreachable: pass
        return None
    return {
        universe: release.get("plugin_count", 0)
        for universe, release in (document.get("universes") or {}).items()
    }


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


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, help="The freshly built index.json")
    parser.add_argument("--previous-url", required=True, help="Published index URL")
    args = parser.parse_args(argv)

    newIndex = json.loads(Path(args.index).read_text(encoding="utf-8"))
    previousCounts = loadPreviousCounts(args.previous_url)
    violations = checkGates(newIndex, previousCounts)
    if violations:
        print("Publish gate failed:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print("Publish gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
