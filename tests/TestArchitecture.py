"""The layers stay isolated: Domain, Data and Controllers import neither
qgis nor Qt (req-mvc-isolation), and the suite itself never needs QGIS
(req-tests-without-qgis).

# @impl 0f87-6ae3-6986-f061
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "SemanticPluginSearch"
PURE_LAYERS = ("Domain", "Data", "Controllers")
FORBIDDEN_MODULES = ("qgis", "PyQt5", "PyQt6", "PyQt", "pyplugin_installer")


def importsOf(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_pure_layers_do_not_import_qgis_or_qt():
    offenders = []
    for layer in PURE_LAYERS:
        for path in (PLUGIN_ROOT / layer).rglob("*.py"):
            forbidden = importsOf(path) & set(FORBIDDEN_MODULES)
            if forbidden:
                offenders.append(f"{path}: {sorted(forbidden)}")
    assert offenders == [], "Import isolation violated:\n" + "\n".join(offenders)


def test_pure_layers_limit_third_party_imports_to_numpy():
    # Explicit allowlist rather than sys.stdlib_module_names: deterministic
    # across Python versions (3.9 has no stdlib_module_names) and stricter.
    allowed = {
        "__future__", "abc", "collections", "dataclasses", "hashlib", "json", "os",
        "pathlib", "sqlite3", "tempfile", "typing", "unicodedata", "urllib",
        "numpy",
    }
    offenders = []
    for layer in PURE_LAYERS:
        for path in (PLUGIN_ROOT / layer).rglob("*.py"):
            extra = importsOf(path) - allowed
            if extra:
                offenders.append(f"{path}: {sorted(extra)}")
    assert offenders == [], "Unexpected third party imports:\n" + "\n".join(offenders)


def test_query_processing_layers_have_no_network_access():
    # The query is tokenized and embedded in Domain and orchestrated in
    # Controllers; without HTTP modules there, the raw query text cannot
    # leave the machine. Data.AssetGateways is the single sanctioned network
    # component and its API only carries URLs and checksums, never queries.
    networkModules = {"urllib", "http", "requests", "socket", "ftplib", "smtplib"}
    offenders = []
    for layer in ("Domain", "Controllers"):
        for path in (PLUGIN_ROOT / layer).rglob("*.py"):
            found = importsOf(path) & networkModules
            if found:
                offenders.append(f"{path}: {sorted(found)}")
    assert offenders == [], "Network access in query processing layers:\n" + "\n".join(offenders)


def test_qt_imports_go_through_the_qgis_indirection_only():
    # Both QGIS 3 (PyQt5) and QGIS 4 (PyQt6) must be served by qgis.PyQt;
    # a direct PyQt5/PyQt6 import would break one of the two.
    offenders = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        direct = importsOf(path) & {"PyQt5", "PyQt6", "PyQt"}
        if direct:
            offenders.append(f"{path}: {sorted(direct)}")
    assert offenders == [], "Direct Qt binding imports:\n" + "\n".join(offenders)


# @impl 0f87-6ae3-6996-386d


def test_qt_and_qgis_enums_use_scoped_access():
    """PyQt6 and QGIS 4 removed unscoped enum access; the scoped form works
    on both PyQt5 and PyQt6, so only scoped forms are allowed."""
    import re

    unscopedPatterns = {
        r"\bQt\.(QueuedConnection|DirectConnection|BlockingQueuedConnection)\b":
            "Qt.ConnectionType.*",
        r"\bQt\.(Horizontal|Vertical)\b": "Qt.Orientation.*",
        r"\bQt\.(UserRole|DisplayRole|EditRole|ToolTipRole|UserCheckRole)\b":
            "Qt.ItemDataRole.*",
        r"\bQt\.(AlignCenter|AlignLeft|AlignRight|AlignTop|AlignBottom|AlignVCenter|AlignHCenter)\b":
            "Qt.AlignmentFlag.*",
        r"\bQt\.(WA_\w+)\b": "Qt.WidgetAttribute.*",
        r"\bQgis\.(Info|Warning|Critical|Success|NoLevel)\b": "Qgis.MessageLevel.*",
    }
    offenders = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern, scopedForm in unscopedPatterns.items():
            for match in re.finditer(pattern, source):
                line = source[: match.start()].count("\n") + 1
                offenders.append(
                    f"{path}:{line}: {match.group(0)} - use {scopedForm}"
                )
    assert offenders == [], "Unscoped enum access (breaks on PyQt6/QGIS 4):\n" + "\n".join(offenders)


def test_message_bar_is_only_touched_by_the_thread_safe_reporter():
    """Pushing a message from a pool thread crashes QGIS on macOS: widgets
    may only be touched from the GUI thread. The message bar is therefore
    confined to MessageBarReporter, which marshals through queued signals.
    """
    offenders = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        if path.name == "Reporter.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "messageBar" in line:
                offenders.append(f"{path}:{number}: {line.strip()}")
    assert offenders == [], "Direct message bar access:\n" + "\n".join(offenders)


def test_reporter_marshals_to_the_gui_thread():
    source = (PLUGIN_ROOT / "QgisBridge" / "Reporter.py").read_text(encoding="utf-8")
    assert "pyqtSignal" in source
    assert "QueuedConnection" in source
    assert "QObject" in source
