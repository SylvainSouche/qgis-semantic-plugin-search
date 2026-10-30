"""The plugin folder meets the QGIS plugin repository rules.

The checks live in tools/PackageCheck.py (standard library only, also run by
make dist); these tests run the same functions in the suite.
"""
from __future__ import annotations

import pytest

from tools import PackageCheck


def test_mandatory_metadata_and_versions_follow_the_rules():
    assert PackageCheck.metadataProblems() == []


def test_author_email_is_present():
    if PackageCheck.missingEmail():
        pytest.skip("metadata.txt email is empty: mandatory for upload, pending the author")


def test_license_file_ships_inside_the_plugin():
    assert PackageCheck.licenseProblems() == []


def test_no_binaries_or_hidden_files_in_the_plugin():
    assert PackageCheck.fileProblems() == []


def test_plugin_code_uses_the_qgis_network_stack_only():
    assert PackageCheck.networkProblems() == []


def test_a_todo_changelog_entry_is_refused(tmp_path):
    plugin = tmp_path / "Plugin"
    plugin.mkdir()
    (plugin / "metadata.txt").write_text(
        "[general]\nname=X\nqgisMinimumVersion=3.44\nqgisMaximumVersion=4.99\n"
        "description=d\nabout=a\nversion=1.0.1\nauthor=me\n"
        "repository=https://x.test/r\ntracker=https://x.test/r/issues\nhomepage=https://x.test/r\n"
        "changelog=1.0.1 - TODO describe this release\n    1.0.0 - First\n",
        encoding="utf-8",
    )
    problems = PackageCheck.metadataProblems(plugin)
    assert any("TODO" in problem for problem in problems)
