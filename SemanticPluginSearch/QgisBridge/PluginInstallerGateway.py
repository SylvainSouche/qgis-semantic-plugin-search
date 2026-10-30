"""Delegation to the standard QGIS plugin manager machinery.

The search window never installs, upgrades or removes anything itself: this
gateway calls the same pyplugin_installer entry points the plugin manager
dialog uses. The API differs across QGIS versions: QGIS 4 exposes
pyplugin_installer.instance() returning a QgsPluginInstaller and has no
reinstallPlugin, while QGIS 3 had a module level installer singleton with
reinstallPlugin, so the gateway resolves the installer lazily at action time
and falls back to opening the plugin manager dialog when nothing matches
(verified against the installed QGIS 4.2.3 source; see
asm-installer-reachable in the project model).
"""
from __future__ import annotations

import time

from qgis.PyQt.QtCore import QEventLoop, QTimer
from qgis.gui import QgisInterface

from ..Data.InstalledPlugins import scanInstalledPlugins
from ..Domain.Entities import InstalledPlugin, PluginInfo
from ..Domain.Installed import installerKey
from ..Domain.Ports import PluginManagerGateway, Reporter


def _spin(seconds: float) -> None:
    """Process events for a short while, keeping the GUI responsive."""
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


class PluginInstallerGateway(PluginManagerGateway):
    """Thin proxy over pyplugin_installer; owns no installation logic."""

    def __init__(self, iface: QgisInterface, reporter: Reporter) -> None:
        self.iface = iface
        self.reporter = reporter

    def install(self, plugin: PluginInfo) -> None:
        key = self._installerKey(plugin)
        self._ensureInstallerData(key)
        self._call("installPlugin", key)

    def upgrade(self, plugin: PluginInfo) -> None:
        # Upgrading is an install of the newer version over the existing one.
        key = self._installerKey(plugin)
        self._ensureInstallerData(key)
        self._call("installPlugin", key)

    def reinstall(self, plugin: PluginInfo) -> None:
        key = self._installerKey(plugin)
        self._ensureInstallerData(key)
        installer = self._resolve()
        if installer is not None and hasattr(installer, "reinstallPlugin"):
            # QGIS 3.x dedicated entry point.
            self._call("reinstallPlugin", key)
        else:
            # QGIS 4.x: installing over an existing installation reinstalls.
            self._call("installPlugin", key)

    def uninstall(self, plugin: PluginInfo) -> None:
        # Uninstalling an installed plugin needs no repository data: the
        # installer falls back to its installed cache.
        self._call("uninstallPlugin", self._installerKey(plugin))

    @staticmethod
    def _installerKey(plugin: PluginInfo) -> str:
        """The key pyplugin_installer knows the plugin by (Domain.Installed)."""
        return installerKey(plugin)

    def _ensureInstallerData(self, key: str, timeout: float = 30.0) -> None:
        """Make the installer's plugin dictionary contain the key.

        The plugin manager populates pyplugin_installer when it opens; since
        we delegate directly, fetch the repositories once and wait, like the
        manager does on start.
        """
        try:
            from pyplugin_installer import installer_data
        except ImportError:
            # No installer data module: delegate anyway and let the installer
            # report its own complaint.
            return

        if key in installer_data.plugins.all():
            return
        repositories = installer_data.repositories
        if not repositories.fetchingInProgress():
            self.reporter.info("Fetching the plugin list…")
            for repositoryKey in repositories.allEnabled():
                repositories.requestFetching(repositoryKey)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not repositories.fetchingInProgress():
                break
            _spin(0.15)
        if key not in installer_data.plugins.all():
            raise RuntimeError(
                f"'{key}' is not in the fetched plugin lists; "
                "open the plugin manager once to refresh them."
            )

    def installedPlugins(self) -> dict[str, InstalledPlugin]:
        """Read the plugin folders QGIS loads from, user profile first.

        qgis.utils.plugin_paths is read at call time (QGIS rebinds its module
        globals), and the folders are scanned rather than trusting
        qgis.utils.plugins (loaded instances only, keyed by folder, without a
        version) or plugins_metadata_parser (never pruned on uninstall).
        """
        import qgis.utils

        paths = list(getattr(qgis.utils, "plugin_paths", []) or [])
        if not paths:
            # QGIS fills plugin_paths during its Python startup; a bare
            # application (headless scripts, the smoke test) leaves it empty.
            from qgis.core import QgsApplication

            paths = [
                QgsApplication.qgisSettingsDirPath().rstrip("/") + "/python/plugins",
                QgsApplication.pkgDataPath().rstrip("/") + "/python/plugins",
            ]
        return scanInstalledPlugins(paths)

    def _resolve(self):
        """The installer instance for this QGIS version, or None.

        Resolution happens at action time: the QGIS 4 entry point
        initializes repository data and can start fetches, which is exactly
        what the plugin manager does when it is used.
        """
        try:
            from pyplugin_installer import instance

            return instance()
        # Not QGIS 4: fall through to the QGIS 3 spelling below.
        except Exception:  # noqa: BLE001  # nosec B110
            pass
        try:
            from pyplugin_installer.installer import installer  # QGIS 3 singleton

            return installer
        except Exception:  # noqa: BLE001 - nothing matches on this QGIS
            return None

    def _call(self, operation: str, pluginName: str) -> None:
        installer = self._resolve()
        method = getattr(installer, operation, None) if installer is not None else None
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
# @impl 4be9-6ae3-f12c-0110
