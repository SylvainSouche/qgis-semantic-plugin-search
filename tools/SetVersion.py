"""Set or increment the plugin version in SemanticPluginSearch/metadata.txt.

    python tools/SetVersion.py --set 0.4.1 [--comment "What changed"]
    python tools/SetVersion.py --increment maj|min|rel [--comment "What changed"]

Versions are MAJOR.MINOR.RELEASE. Incrementing a part resets the parts after
it (0.4.1 + min -> 0.5.0). The new version gets a changelog entry at the top
of the changelog: "<version> - <comment>", or without a comment
"<version> - TODO describe this release". The QGIS plugin repository
requires a changelog for updates, and TestPluginRepositoryRules (so
`make dist`) refuses to package while the current version's entry still
says TODO.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

METADATA = Path(__file__).resolve().parents[1] / "SemanticPluginSearch" / "metadata.txt"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PARTS = ("maj", "min", "rel")
TODO_MARK = "TODO describe this release"


class VersionError(ValueError):
    """An invalid version, increment or metadata file."""


def parseVersion(text: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(text.strip())
    if not match:
        raise VersionError(f"not a MAJOR.MINOR.RELEASE version: {text!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def incremented(current: str, part: str) -> str:
    if part not in PARTS:
        raise VersionError(f"inc must be one of {', '.join(PARTS)}, not {part!r}")
    major, minor, release = parseVersion(current)
    if part == "maj":
        return f"{major + 1}.0.0"
    if part == "min":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{release + 1}"


def currentVersion(metadata: str) -> str:
    match = re.search(r"^version=(.*)$", metadata, re.M)
    if not match:
        raise VersionError("metadata.txt has no version line")
    return match.group(1).strip()


def withVersion(metadata: str, version: str, comment: str = "") -> str:
    """The metadata text with the new version and its changelog entry on top."""
    parseVersion(version)
    current = currentVersion(metadata)
    if version == current:
        raise VersionError(f"the version is already {version}")
    text = re.sub(r"^version=.*$", f"version={version}", metadata, count=1, flags=re.M)
    match = re.search(r"^changelog=(.*)$", text, re.M)
    comment = " ".join(comment.split())  # one line: the changelog is line based
    stub = f"{version} - {comment or TODO_MARK}"
    if match:
        text = (
            text[: match.start()]
            + f"changelog={stub}\n    {match.group(1)}"
            + text[match.end():]
        )
    else:
        text = text.rstrip("\n") + f"\nchangelog={stub}\n"
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", metavar="VERSION")
    group.add_argument("--increment", metavar="PART", help="maj, min or rel")
    parser.add_argument("--comment", default="", help="Changelog entry for the new version")
    parser.add_argument("--metadata", default=str(METADATA))
    args = parser.parse_args(argv)

    path = Path(args.metadata)
    metadata = path.read_text(encoding="utf-8")
    try:
        current = currentVersion(metadata)
        version = args.set if args.set else incremented(current, args.increment)
        path.write_text(withVersion(metadata, version, args.comment), encoding="utf-8")
    except VersionError as error:
        print(f"Version unchanged: {error}", file=sys.stderr)
        return 1
    print(f"==> Version {current} -> {version}")
    if args.comment.strip():
        print(f"==> Changelog: {version} - {' '.join(args.comment.split())}")
        return 0
    print(f"==> Now describe it: edit the '{version} - {TODO_MARK}' changelog entry")
    print(f"    in {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path},")
    print('    or pass COMMENT="..." next time; make dist refuses to package until it is written.')
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 4be9-6ae4-471f-260f
