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

import inspect
import re
import time

from qgis.core import Qgis
from qgis.PyQt.QtCore import QEventLoop, QTimer
from qgis.gui import QgisInterface

from ..Data.InstalledPlugins import scanInstalledPlugins
from ..Domain.Entities import InstalledPlugin, PluginInfo
from ..Domain.Installed import installerKey
from ..Domain.Ports import PluginManagerGateway, Reporter
from .Reporter import TITLE


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
        self._call("installPlugin", key, versioned=True)

    def upgrade(self, plugin: PluginInfo) -> None:
        # Upgrading is an install of the newer version over the existing one.
        key = self._installerKey(plugin)
        self._ensureInstallerData(key)
        self._call("installPlugin", key, versioned=True)

    def reinstall(self, plugin: PluginInfo) -> None:
        key = self._installerKey(plugin)
        self._ensureInstallerData(key)
        installer = self._resolve()
        if installer is not None and hasattr(installer, "reinstallPlugin"):
            # QGIS 3.x dedicated entry point.
            self._call("reinstallPlugin", key, versioned=True)
        else:
            # QGIS 4.x: installing over an existing installation reinstalls.
            self._call("installPlugin", key, versioned=True)

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
        # The fetched lists land in the repository cache; like the plugin
        # manager, rebuild to publish them in plugins.all().
        installer_data.plugins.rebuild()
        if key in installer_data.plugins.all():
            return
        raise RuntimeError(_whyNotInstallable(installer_data, key))

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

    def _call(self, operation: str, pluginName: str, versioned: bool = False) -> None:
        installer = self._resolve()
        method = getattr(installer, operation, None) if installer is not None else None
        if method is None:
            self._openManagerFallback(pluginName, operation)
            return
        # The installer reports its own failures to the QGIS message bar only;
        # catch them so they reach the user as this plugin's error popup.
        with _InstallerFailures() as failures:
            method(pluginName, **(_versionOptions(pluginName, method) if versioned else {}))
        if failures.messages:
            raise RuntimeError(" ".join(failures.messages))

    def _openManagerFallback(self, pluginName: str, operation: str) -> None:
        # Unknown installer API on this QGIS version: open the manager so the
        # user performs the action there.
        show = getattr(self.iface, "showPluginManager", None)
        if show is not None:
            show()
        self.reporter.info(
            f"Please {operation} '{pluginName}' in the plugin manager."
        )


def _whyNotInstallable(installer_data, key: str) -> str:  # noqa: ANN001 - module
    """Explain why the installer does not offer the plugin.

    The installer only publishes experimental (and deprecated) plugins when
    the plugin manager's "Show also experimental plugins" (and "Show also
    deprecated plugins") settings are ticked; the search window can show
    them anyway, so say which setting is needed instead of a bare KeyError.
    """
    cached = [
        plugin
        for plugins in getattr(installer_data.plugins, "repoCache", {}).values()
        for plugin in plugins
        if plugin.get("id") == key
    ]
    if cached:
        if all(plugin.get("experimental") for plugin in cached):
            return (
                f"'{key}' is experimental: the plugin manager installs it only when "
                "'Show also experimental plugins' is ticked in its Settings tab."
            )
        if all(plugin.get("deprecated") for plugin in cached):
            return (
                f"'{key}' is deprecated: the plugin manager installs it only when "
                "'Show also deprecated plugins' is ticked in its Settings tab."
            )
    return (
        f"'{key}' is not in the plugin lists the plugin manager fetched; "
        "open the plugin manager once to refresh them, and check that it is "
        "available for this QGIS version."
    )


def _versionOptions(key: str, method) -> dict:  # noqa: ANN001 - installer method
    """stable=False for a plugin that only has an experimental version.

    installPlugin(key) installs the stable version by default; for a plugin
    published only as experimental its stable download URL is empty and the
    installer fails with 'Protocol "" is unknown'. The plugin manager passes
    stable=False in that case, and so do we, when the method accepts it.
    A plugin with a stable version keeps the stable default, as in the
    plugin manager.
    """
    try:
        from pyplugin_installer import installer_data

        entry = installer_data.plugins.all().get(key) or {}
    except Exception:  # noqa: BLE001 - no installer data: keep the defaults
        return {}
    if entry.get("download_url_stable") or not entry.get("download_url_experimental"):
        return {}
    try:
        accepted = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return {}
    return {"stable": False} if "stable" in accepted else {}


class _InstallerFailures:
    """Collects the critical messages QGIS logs while an installer call runs.

    pyplugin_installer pushes "Plugin installation failed: ..." to the
    plugin manager's message bar, which logs it; the call itself returns
    normally. Messages of this plugin (prefixed with its title) are ignored.
    The installer runs on the GUI thread, so the log signal is delivered
    synchronously while the call is in progress.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        self._log = None

    def __enter__(self) -> _InstallerFailures:
        try:
            from qgis.core import QgsApplication

            self._log = QgsApplication.messageLog()
            self._log.messageReceived.connect(self._collect)
        except Exception:  # noqa: BLE001 - no log available: report nothing extra
            self._log = None
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        if self._log is not None:
            try:
                self._log.messageReceived.disconnect(self._collect)
            except Exception:  # noqa: BLE001  # nosec B110
                pass

    def _collect(self, *args) -> None:  # noqa: ANN002 - (message, tag, level)
        if len(args) != 3:
            return
        message, _tag, level = args
        if level != Qgis.MessageLevel.Critical:
            return
        text = " ".join(re.sub(r"<[^>]+>", "", str(message)).split())
        if text and not text.startswith(TITLE) and text not in self.messages:
            self.messages.append(text)


# @impl 4be9-6ae3-f12c-0110
# @impl 4be9-6ae4-4926-4fb9
# @impl 4be9-6ae4-4b88-00cf
# @impl 4be9-6ae4-4c75-c7ae
