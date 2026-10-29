"""Delegation to the standard QGIS plugin manager machinery.

The search window never installs, upgrades or removes anything itself: this
gateway calls the same pyplugin_installer entry points the plugin manager
dialog uses. The exact callable names differ slightly across QGIS major
versions, so the adapter resolves them defensively and falls back to opening
the plugin manager dialog when a direct call is unavailable
(see asm-installer-reachable in the project model).
"""
from __future__ import annotations

from qgis.gui import QgisInterface

from ..Domain.Entities import ActionStates
from ..Domain.Ports import PluginManagerGateway, Reporter


class PluginInstallerGateway(PluginManagerGateway):
    """Thin proxy over pyplugin_installer; owns no installation logic."""

    def __init__(self, iface: QgisInterface, reporter: Reporter) -> None:
        self.iface = iface
        self.reporter = reporter

    def install(self, pluginName: str) -> None:
        self._call("installPlugin", pluginName)

    def upgrade(self, pluginName: str) -> None:
        # Upgrading is an install of the newer version over the existing one.
        self._call("installPlugin", pluginName)

    def reinstall(self, pluginName: str) -> None:
        self._call("reinstallPlugin", pluginName)

    def uninstall(self, pluginName: str) -> None:
        self._call("uninstallPlugin", pluginName)

    def actionStates(self, pluginName: str, availableVersion: str) -> ActionStates:
        installed = _installedVersion(pluginName)
        if not installed:
            return ActionStates(canInstall=True)
        upgradeable = _versionIsNewer(availableVersion, installed)
        return ActionStates(
            canUpgrade=upgradeable,
            canReinstall=True,
            canUninstall=True,
            installedVersion=installed,
        )

    def _call(self, operation: str, pluginName: str) -> None:
        installer = _pluginInstaller()
        method = getattr(installer, operation, None)
        if method is None:
            self._openManagerFallback(pluginName, operation)
            return
        method(pluginName)

    def _openManagerFallback(self, pluginName: str, operation: str) -> None:
        # Unknown installer API on this QGIS version: open the manager so the
        # user performs the action there.
        show = getattr(self.iface, "showPluginManager", None)
        if show is not None:
            show()
        self.reporter.info(
            f"Please {operation} '{pluginName}' in the plugin manager."
        )


def _pluginInstaller():
    from pyplugin_installer.installer import installer

    return installer


def _installedVersion(pluginName: str) -> str:
    import qgis.utils

    plugin = qgis.utils.plugins.get(pluginName)
    if plugin is not None:
        return str(getattr(plugin, "version", "") or "")
    metadata = getattr(qgis.utils, "plugin_metadata", {}).get(pluginName)
    if metadata is not None:
        return str(getattr(metadata, "version", "") or "")
    return ""


def _versionIsNewer(candidate: str, installed: str) -> bool:
    def parts(version: str) -> tuple[int, ...]:
        chunks = []
        for chunk in version.split("."):
            digits = "".join(character for character in chunk if character.isdigit())
            chunks.append(int(digits) if digits else 0)
        return tuple(chunks)

    return parts(candidate or "0") > parts(installed or "0")

# @impl 0f87-6ae3-6996-c732
