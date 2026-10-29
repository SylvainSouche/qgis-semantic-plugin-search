"""QGIS plugin entry point.

Semantic Plugin Search: find QGIS plugins with natural language queries.

Naming convention: UpperCamelCase classes and modules, Qt style camelCase
methods, matching the surrounding PyQt ecosystem.

# @impl 0f87-6ae3-6986-14e6
"""
from __future__ import annotations

def classFactory(iface):  # noqa: ANN001 - QGIS plugin API
    from .PluginEntry import SemanticPluginSearchPlugin

    return SemanticPluginSearchPlugin(iface)
