"""Version bumps (tools/SetVersion.py, make version / make increment)."""
from __future__ import annotations

import pytest

from tools.SetVersion import (
    TODO_MARK,
    VersionError,
    incremented,
    main,
    withChangelogEntry,
    withVersion,
)

METADATA = """; @impl x
[general]
name=Semantic Plugin Search
version=0.4.0
changelog=0.4.0 - Fixes
    0.3.0 - Hardening
"""


@pytest.mark.parametrize(
    ("part", "expected"), [("maj", "1.0.0"), ("min", "0.5.0"), ("rel", "0.4.1")]
)
def test_increments_reset_the_lower_parts(part, expected):  # noqa: ANN001
    assert incremented("0.4.0", part) == expected


def test_an_unknown_part_or_version_is_refused():
    with pytest.raises(VersionError):
        incremented("0.4.0", "patch")
    with pytest.raises(VersionError):
        withVersion(METADATA, "0.5")
    with pytest.raises(VersionError, match="already"):
        withVersion(METADATA, "0.4.0")


def test_the_new_version_gets_a_changelog_entry_to_fill_in():
    text = withVersion(METADATA, "0.4.1")
    assert "version=0.4.1\n" in text
    assert f"changelog=0.4.1 - {TODO_MARK}\n    0.4.0 - Fixes\n    0.3.0 - Hardening" in text
    assert text.startswith("; @impl x\n[general]")


def test_the_cli_rewrites_the_file(tmp_path):
    metadata = tmp_path / "metadata.txt"
    metadata.write_text(METADATA, encoding="utf-8")
    assert main(["--increment", "min", "--metadata", str(metadata),
                 "--changelog", str(tmp_path / "none.md")]) == 0
    assert "version=0.5.0" in metadata.read_text(encoding="utf-8")
    assert main(["--set", "bad", "--metadata", str(metadata),
                 "--changelog", str(tmp_path / "none.md")]) == 1
    assert "version=0.5.0" in metadata.read_text(encoding="utf-8")


def test_a_comment_becomes_the_changelog_entry():
    text = withVersion(METADATA, "0.4.1", "Coloured  installed\n badges")
    assert "changelog=0.4.1 - Coloured installed badges\n    0.4.0 - Fixes" in text
    assert TODO_MARK not in text


def test_the_cli_accepts_a_comment(tmp_path):
    metadata = tmp_path / "metadata.txt"
    metadata.write_text(METADATA, encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert main(["--increment", "rel", "--comment", "Badges", "--metadata", str(metadata),
                 "--changelog", str(changelog)]) == 0
    assert "changelog=0.4.1 - Badges" in metadata.read_text(encoding="utf-8")
    assert "- **0.4.1** (" in changelog.read_text(encoding="utf-8")


CHANGELOG = """# Changelog

Intro.

## 0.4: Fixes

Released.

- **0.4.0** (2026-10-30): Fixes

## 0.3: Hardening

- **0.3.0** (2026-10-30): Hardening
"""


def test_a_release_joins_its_series_in_the_changelog():
    text = withChangelogEntry(CHANGELOG, "0.4.1", "Badges", "2026-11-23")
    assert "Released.\n\n- **0.4.1** (2026-11-23): Badges\n- **0.4.0**" in text


def test_a_new_series_gets_its_own_heading():
    text = withChangelogEntry(CHANGELOG, "0.5.0", "", "2026-11-23")
    assert f"Intro.\n\n## 0.5\n\n- **0.5.0** (2026-11-23): {TODO_MARK}\n\n## 0.4: Fixes" in text
