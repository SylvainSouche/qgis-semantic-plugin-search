"""Every private attribute a plugin class reads must be defined by that class.

Presentation and QgisBridge cannot be imported without qgis, so a slot that
is connected but missing (self.linksView.anchorClicked.connect(self._openLink)
without a _openLink method) only fails when the window opens inside QGIS.
That exact defect shipped in the 0.3.0 package. This test parses every plugin
module statically: each self._name read inside a class must be a method, a
class attribute or an attribute assigned on self somewhere in that class or
in a base class defined in the same module. No qgis or Qt import happens.
"""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "SemanticPluginSearch"


def definedNames(cls: ast.ClassDef) -> set[str]:
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


def privateReads(cls: ast.ClassDef) -> list[tuple[int, str]]:
    reads = []
    for node in ast.walk(cls):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr.startswith("_")
            and not node.attr.startswith("__")
        ):
            reads.append((node.lineno, node.attr))
    return reads


def test_every_private_self_attribute_read_is_defined():
    problems = []
    for path in sorted(PLUGIN_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        for cls in classes.values():
            defined = definedNames(cls)
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id in classes:
                    defined |= definedNames(classes[base.id])
            for line, name in privateReads(cls):
                if name not in defined:
                    relative = path.relative_to(PLUGIN_ROOT.parent)
                    problems.append(f"{relative}:{line} {cls.name} reads self.{name}")
    assert not problems, "undefined private attributes:\n" + "\n".join(problems)
# @impl 4be9-6ae4-41dc-de55
