"""Every relative import inside the plugin must resolve.

The suite cannot import PluginEntry, Presentation or QgisBridge (they need
qgis/Qt), so a broken import in the composition root only surfaces inside
QGIS. This test parses every plugin module statically and verifies that each
relative import points at an existing module and that the imported names are
actually defined there. No qgis or Qt import happens.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "SemanticPluginSearch"


def topLevelNames(tree: ast.Module) -> set[str]:
    """Names importable from a module: defs, classes, assignments, imports."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.If):
            for inner in node.body + node.orelse:
                if isinstance(inner, (ast.FunctionDef, ast.ClassDef)):
                    names.add(inner.name)
                elif isinstance(inner, ast.ImportFrom):
                    names.update(alias.asname or alias.name for alias in inner.names)
                elif isinstance(inner, ast.Import):
                    names.update(alias.asname or alias.name.split(".")[0] for alias in inner.names)
    return names


def moduleFile(moduleParts: tuple[str, ...]) -> Path | None:
    candidate = PLUGIN_ROOT.joinpath(*moduleParts)
    if candidate.is_dir():
        return candidate / "__init__.py" if (candidate / "__init__.py").is_file() else candidate
    if candidate.with_suffix(".py").is_file():
        return candidate.with_suffix(".py")
    return None


def relativeBase(packageParts: tuple[str, ...], level: int) -> tuple[str, ...]:
    # level 1 = the containing package, level 2 = its parent, ...
    if level - 1 > len(packageParts):
        return ("..",)  # escapes the plugin root; reported as not found
    return packageParts[: len(packageParts) - (level - 1)]


def test_relative_imports_resolve():
    offenders: list[str] = []
    for path in sorted(PLUGIN_ROOT.rglob("*.py")):
        # The containing package: for __init__.py the directory itself, for
        # any other module the directory it lives in.
        packageParts = tuple(path.parent.relative_to(PLUGIN_ROOT).parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            base = relativeBase(packageParts, node.level)
            target = (*base, *(node.module or "").split(".")) if node.module else base
            target = tuple(part for part in target if part)
            resolved = moduleFile(target)
            if resolved is None:
                offenders.append(f"{path}: from {'.' * node.level}{node.module or ''} -> module not found")
                continue
            if resolved.is_dir():
                # from package import submodule: check each name is a module
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if moduleFile((*target, alias.name)) is None:
                        offenders.append(f"{path}: {alias.name} not found in package {'.'.join(target)}")
                continue
            names = topLevelNames(ast.parse(resolved.read_text(encoding="utf-8")))
            for alias in node.names:
                if alias.name == "*":
                    continue
                if alias.name not in names:
                    offenders.append(
                        f"{path}: {alias.name} not defined in {'.'.join(target)}"
                    )
    assert offenders == [], "Broken relative imports:\n" + "\n".join(offenders)
