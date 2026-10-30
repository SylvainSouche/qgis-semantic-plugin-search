"""Action orchestration: forward manager actions to the plugin manager.

The controller holds no installation logic whatsoever: every operation is
delegated to the PluginManagerGateway, whose QGIS adapter calls the standard
plugin manager machinery. What the window shows about installed plugins (the
action buttons and the installed badges) is computed by the Domain from a
fresh on disk snapshot, and refreshed after every action.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import ActionStates, InstalledPlugin, PluginInfo, SearchResult
from ..Domain.Installed import actionStatesFor, installedBadges
from ..Domain.Ports import PluginManagerGateway, Reporter
from .ViewPorts import SearchWindowView


class ActionController:
    """Forwards manager actions to the plugin manager gateway."""

    def __init__(
        self,
        gateway: PluginManagerGateway,
        reporter: Reporter,
    ) -> None:
        self.gateway = gateway
        self.reporter = reporter
        self._shownResults: list[SearchResult] = []

    def runAction(self, view: SearchWindowView, action: str, info: PluginInfo | None) -> None:
        if info is None:
            view.showStatus("Select a plugin first.")
            return
        handlers = {
            "install": (self.gateway.install, "Installing"),
            "upgrade": (self.gateway.upgrade, "Upgrading"),
            "reinstall": (self.gateway.reinstall, "Reinstalling"),
            "uninstall": (self.gateway.uninstall, "Uninstalling"),
        }
        handler = handlers.get(action)
        if handler is None:
            view.showStatus(f"Unknown action: {action}")
            return
        operation, label = handler
        view.showStatus(f"{label} {info.name} through the plugin manager…")
        try:
            operation(info)
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            self.reporter.error(f"{label} {info.name} failed: {error}")
            view.showStatus(f"{label} failed: {error}")
            return
        view.showStatus(f"{label} handed to the plugin manager.")
        # The manager may have changed what is installed (or the user may have
        # cancelled its confirmation): re-read the disk, never assume.
        installed = self._snapshot()
        view.setActionStates(self._statesFrom(info, installed))
        view.showInstalledBadges(
            installedBadges((r.info for r in self._shownResults), installed or {})
        )

    def refreshStates(self, view: SearchWindowView, info: PluginInfo | None) -> None:
        """Ask the disk which actions apply to the current selection."""
        if info is None:
            view.setActionStates(ActionStates())
            return
        view.setActionStates(self._statesFrom(info, self._snapshot()))

    def refreshInstalled(self, view: SearchWindowView, results: list[SearchResult]) -> None:
        """Badge the installed plugins among the rows just shown."""
        self._shownResults = list(results)
        view.showInstalledBadges(installedBadges((r.info for r in results), self._snapshot() or {}))

    def _snapshot(self) -> dict[str, InstalledPlugin] | None:
        """The installed plugins, or None when the state cannot be read."""
        try:
            return self.gateway.installedPlugins()
        except Exception as error:  # noqa: BLE001 - conservative fallback
            self.reporter.warn(f"Installed plugins unavailable: {error}")
            return None

    @staticmethod
    def _statesFrom(
        info: PluginInfo, installed: dict[str, InstalledPlugin] | None
    ) -> ActionStates:
        # Unknown state disables every button rather than offering Install
        # for a plugin that may well be installed.
        return ActionStates() if installed is None else actionStatesFor(info, installed)

# @impl 0f87-6ae3-6985-0cec
# @impl 0f87-6ae3-6996-c732
# @impl 4be9-6ae3-f12c-0110
