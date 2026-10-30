"""Snapshot of the plugins installed on disk.

QGIS keeps its own lists (qgis.utils.available_plugins and
plugins_metadata_parser) but they go stale: uninstalling never drops the
metadata entry, so they keep reporting removed plugins. The folders are the
truth, so the snapshot reads each plugin folder's metadata.txt directly, the
same way qgis.utils.findPlugins does.

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import configparser
from collections.abc import Iterable
from pathlib import Path

from ..Domain.Entities import InstalledPlugin


def scanInstalledPlugins(pluginPaths: Iterable[str | Path]) -> dict[str, InstalledPlugin]:
    """Installed plugins by folder key; the first path wins, like QGIS.

    Unreadable folders and folders without a metadata.txt are skipped.
    """
    installed: dict[str, InstalledPlugin] = {}
    for root in pluginPaths:
        rootPath = Path(root)
        if not rootPath.is_dir():
            continue
        for folder in sorted(rootPath.iterdir()):
            key = folder.name
            if key in installed or not folder.is_dir():
                continue
            metadataPath = folder / "metadata.txt"
            if not metadataPath.is_file():
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(metadataPath, encoding="utf-8")
                name = parser.get("general", "name", fallback="")
                version = parser.get("general", "version", fallback="")
            except (configparser.Error, OSError, UnicodeDecodeError):
                continue
            installed[key] = InstalledPlugin(key=key, name=name.strip(), version=version.strip())
    return installed
# @impl 4be9-6ae3-f12c-0110
