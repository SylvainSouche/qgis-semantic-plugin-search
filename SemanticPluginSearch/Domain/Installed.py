"""Installed state of plugins and the manager actions it allows.

Pure logic: the QGIS adapter supplies a snapshot of what is installed on
disk, and everything that decides what the window shows (the action buttons,
the installed badge) is computed here, where it is tested without QGIS.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .Entities import ActionStates, InstalledPlugin, PluginInfo

BADGE_INSTALLED = "installed"
BADGE_UPGRADEABLE = "upgradeable"


def installerKey(info: PluginInfo) -> str:
    """The key pyplugin_installer knows the plugin by.

    The installer derives keys from the package file name (e.g.
    topoprofilestudio.1.0.0.zip gives topoprofilestudio), not from the
    display name, so the two can differ in case and spacing. The installed
    plugin folder carries the same key.
    """
    if info.fileName:
        return info.fileName.partition(".")[0]
    return info.name


def findInstalled(
    info: PluginInfo, installed: Mapping[str, InstalledPlugin]
) -> InstalledPlugin | None:
    """The installed copy of the plugin, matched by key, then by name.

    Exact installer key first; then the key case insensitively (folders
    unpacked on case insensitive file systems); then the display name the
    installed metadata.txt declares, for packages whose folder differs from
    their file name.
    """
    key = installerKey(info)
    if key in installed:
        return installed[key]
    lowered = key.lower()
    for candidateKey, plugin in installed.items():
        if candidateKey.lower() == lowered:
            return plugin
    for plugin in installed.values():
        if plugin.name and plugin.name == info.name:
            return plugin
    return None


def versionIsNewer(candidate: str, installed: str) -> bool:
    """True when candidate is a strictly newer dotted version than installed."""

    def parts(version: str) -> tuple[int, ...]:
        chunks = []
        for chunk in version.split("."):
            digits = "".join(character for character in chunk if character.isdigit())
            chunks.append(int(digits) if digits else 0)
        while len(chunks) > 1 and chunks[-1] == 0:
            chunks.pop()
        return tuple(chunks)

    return parts(candidate or "0") > parts(installed or "0")


def actionStatesFor(
    info: PluginInfo, installed: Mapping[str, InstalledPlugin]
) -> ActionStates:
    """Which manager actions apply: Install when absent, else the other three."""
    copy = findInstalled(info, installed)
    if copy is None:
        return ActionStates(canInstall=True)
    return ActionStates(
        canUpgrade=versionIsNewer(info.version, copy.version),
        canReinstall=True,
        canUninstall=True,
        installedVersion=copy.version,
    )


def installedBadges(
    infos: Iterable[PluginInfo], installed: Mapping[str, InstalledPlugin]
) -> dict[int, str]:
    """Badge per installed plugin id: upgradeable when the catalogue is newer."""
    badges: dict[int, str] = {}
    for info in infos:
        copy = findInstalled(info, installed)
        if copy is not None:
            badges[info.pluginId] = (
                BADGE_UPGRADEABLE if versionIsNewer(info.version, copy.version) else BADGE_INSTALLED
            )
    return badges
# @impl 4be9-6ae3-f12c-0110
# @impl 4be9-6ae4-4682-9629
