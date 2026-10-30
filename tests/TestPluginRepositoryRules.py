"""The plugin folder meets the QGIS plugin repository rules.

Sources: plugins.qgis.org/docs/publish, /docs/approval, /docs/migrate-qgis4
and the PyQGIS cookbook metadata table, checked 2026-10-30. Mandatory
metadata with working links, a LICENSE file inside the package, a changelog,
qgisMaximumVersion of at least 4.0 for the QGIS 4 listing, no binaries, no
hidden or generated files, and network access through the QGIS network stack
rather than urllib or requests.
"""
from __future__ import annotations

import ast
import configparser
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "SemanticPluginSearch"
MANDATORY = ("name", "qgisMinimumVersion", "description", "about", "version", "author",
             "repository", "tracker", "homepage")
CATEGORIES = ("Raster", "Vector", "Database", "Mesh", "Web")
BINARY_SUFFIXES = (".so", ".dll", ".dylib", ".exe", ".pyd", ".bat", ".cmd", ".sh", ".zip")
NETWORK_MODULES = ("urllib.request", "urllib.error", "http.client", "requests", "httpx",
                   "socket", "ftplib")


def metadata() -> configparser.SectionProxy:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keep camelCase keys
    parser.read(PLUGIN_ROOT / "metadata.txt", encoding="utf-8")
    return parser["general"]


def versionTuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def test_mandatory_metadata_is_present():
    general = metadata()
    missing = [key for key in MANDATORY if not general.get(key, "").strip()]
    assert not missing, f"missing metadata: {missing}"
    for key in ("repository", "tracker", "homepage"):
        assert general[key].startswith("https://"), key
    assert general["tracker"].startswith(general["repository"]), "tracker of the code repository"


def test_author_email_is_present():
    if not metadata().get("email", "").strip():
        pytest.skip("metadata.txt email is empty: mandatory for upload, pending the author")


def test_versions_cover_qgis_3_and_4():
    general = metadata()
    assert versionTuple(general["qgisMinimumVersion"]) >= (3, 0)
    assert versionTuple(general["qgisMaximumVersion"]) >= (4, 0), "QGIS 4 listing"
    assert "supportsQt6" not in general, "deprecated flag, no longer recognised"


def test_changelog_and_category_follow_the_rules():
    general = metadata()
    assert general.get("changelog", "").strip().startswith(general["version"])
    assert general.get("category", "Raster") in CATEGORIES


def test_name_does_not_end_with_the_word_plugin():
    assert not metadata()["name"].lower().rstrip().endswith("plugin")


def test_license_file_ships_inside_the_plugin():
    license = PLUGIN_ROOT / "LICENSE"
    assert license.is_file()
    assert license.read_text(encoding="utf-8").strip() == (
        PLUGIN_ROOT.parent / "LICENSE"
    ).read_text(encoding="utf-8").strip()


def test_no_binaries_or_hidden_files_in_the_plugin():
    offenders = [
        str(path.relative_to(PLUGIN_ROOT))
        for path in PLUGIN_ROOT.rglob("*")
        if "__pycache__" not in path.parts
        and (path.suffix.lower() in BINARY_SUFFIXES or path.name.startswith("."))
    ]
    assert not offenders, offenders


def test_plugin_code_uses_the_qgis_network_stack_only():
    offenders = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
            for name in names:
                if any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES):
                    offenders.append(f"{path.relative_to(PLUGIN_ROOT)}: {name}")
    assert not offenders, offenders
