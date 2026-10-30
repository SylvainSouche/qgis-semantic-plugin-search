"""Pre-flight checks of the plugin folder before packaging (make dist).

Standard library only: no venv, numpy or pytest needed, so `make dist` runs
with whatever python3 / python the system has (Cygwin and Windows included).
The same functions back tests/TestPluginRepositoryRules.py and
tests/TestSelfAttributes.py, so `make test` and `make dist` apply one set of
rules.

Checks, from the QGIS plugin repository rules (plugins.qgis.org/docs/publish,
/docs/approval, /docs/migrate-qgis4, checked 2026-10-30) and from defects
that reached QGIS before:

- mandatory metadata with https links to the code repository and its tracker;
- qgisMaximumVersion of at least 4.0, no deprecated supportsQt6 flag;
- a changelog opening with the current version, not a TODO placeholder;
- an allowed category, a name not ending with the word plugin;
- a LICENSE identical to the repository one inside the plugin folder;
- no binaries or hidden files;
- network access through the QGIS network stack only;
- every private attribute a class reads is defined (the 0.3.0 package
  shipped MetadataPanel connecting self._openLink before it existed).

Usage: python tools/PackageCheck.py   (exit 1 on any problem)
"""
from __future__ import annotations

import ast
import configparser
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "SemanticPluginSearch"
MANDATORY = (
    "name", "qgisMinimumVersion", "description", "about", "version", "author",
    "repository", "tracker", "homepage",
)
CATEGORIES = ("Raster", "Vector", "Database", "Mesh", "Web")
BINARY_SUFFIXES = (".so", ".dll", ".dylib", ".exe", ".pyd", ".bat", ".cmd", ".sh", ".zip")
NETWORK_MODULES = (
    "urllib.request", "urllib.error", "http.client", "requests", "httpx", "socket", "ftplib",
)


def metadata(pluginRoot: Path = PLUGIN_ROOT) -> configparser.SectionProxy:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keep camelCase keys
    parser.read(pluginRoot / "metadata.txt", encoding="utf-8")
    return parser["general"]


def versionTuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def metadataProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    general = metadata(pluginRoot)
    problems = [f"missing metadata: {key}" for key in MANDATORY if not general.get(key, "").strip()]
    for key in ("repository", "tracker", "homepage"):
        if general.get(key) and not general[key].startswith("https://"):
            problems.append(f"{key} is not an https link")
    if general.get("tracker") and not general["tracker"].startswith(general.get("repository", "")):
        problems.append("the tracker is not the code repository's")
    try:
        if versionTuple(general.get("qgisMaximumVersion", "0")) < (4, 0):
            problems.append("qgisMaximumVersion below 4.0: not listed for QGIS 4")
    except ValueError:
        problems.append("qgisMaximumVersion is not a dotted version")
    if "supportsQt6" in general:
        problems.append("supportsQt6 is deprecated and no longer recognised")
    changelog = general.get("changelog", "").strip()
    if not changelog.startswith(general.get("version", "?")):
        problems.append("the changelog does not open with the current version")
    elif "TODO" in changelog.splitlines()[0]:
        problems.append(
            "the current version's changelog entry is still a TODO: describe the release "
            '(or bump with make increment INC=... COMMENT="...")'
        )
    if general.get("category", "Raster") not in CATEGORIES:
        problems.append(f"category must be one of {', '.join(CATEGORIES)}")
    if general.get("name", "").lower().rstrip().endswith("plugin"):
        problems.append("the name must not end with the word plugin")
    return problems


def missingEmail(pluginRoot: Path = PLUGIN_ROOT) -> bool:
    return not metadata(pluginRoot).get("email", "").strip()


def licenseProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    license = pluginRoot / "LICENSE"
    if not license.is_file():
        return ["no LICENSE file inside the plugin folder"]
    repositoryLicense = pluginRoot.parent / "LICENSE"
    if license.read_text(encoding="utf-8").strip() != repositoryLicense.read_text(
        encoding="utf-8"
    ).strip():
        return ["the plugin LICENSE differs from the repository LICENSE"]
    return []


def fileProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    return [
        f"binary or hidden file: {path.relative_to(pluginRoot)}"
        for path in pluginRoot.rglob("*")
        if "__pycache__" not in path.parts
        and (path.suffix.lower() in BINARY_SUFFIXES or path.name.startswith("."))
    ]


def networkProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    problems = []
    for path in pluginRoot.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
            for name in names:
                if any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES):
                    problems.append(
                        f"network library outside the QGIS stack: "
                        f"{path.relative_to(pluginRoot)}: {name}"
                    )
    return problems


def _definedNames(cls: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    for node in ast.walk(cls):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for target in targets:
            for element in ast.walk(target):
                if (
                    isinstance(element, ast.Attribute)
                    and isinstance(element.value, ast.Name)
                    and element.value.id == "self"
                ):
                    names.add(element.attr)
    return names


def _privateReads(cls: ast.ClassDef) -> list[tuple[int, str]]:
    return [
        (node.lineno, node.attr)
        for node in ast.walk(cls)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr.startswith("_")
        and not node.attr.startswith("__")
    ]


def selfAttributeProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    problems = []
    for path in sorted(pluginRoot.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        for cls in classes.values():
            defined = _definedNames(cls)
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id in classes:
                    defined |= _definedNames(classes[base.id])
            for line, name in _privateReads(cls):
                if name not in defined:
                    relative = path.relative_to(pluginRoot.parent)
                    problems.append(f"{relative}:{line} {cls.name} reads undefined self.{name}")
    return problems


def allProblems(pluginRoot: Path = PLUGIN_ROOT) -> list[str]:
    return (
        metadataProblems(pluginRoot)
        + licenseProblems(pluginRoot)
        + fileProblems(pluginRoot)
        + networkProblems(pluginRoot)
        + selfAttributeProblems(pluginRoot)
    )


def main() -> int:
    problems = allProblems()
    if missingEmail():
        print("warning: metadata.txt email is empty; plugins.qgis.org requires it for upload")
    if problems:
        print("Package check failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("==> Package check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 4be9-6ae4-4ed4-e450
