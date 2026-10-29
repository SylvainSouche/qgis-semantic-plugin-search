"""Action orchestration: forward manager actions to the plugin manager.

The controller holds no installation logic whatsoever: every operation is
delegated to the PluginManagerGateway, whose QGIS adapter calls the standard
plugin manager machinery.

This module is part of the Controllers layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

from ..Domain.Entities import ActionStates, PluginInfo
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
            operation(info.name)
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            self.reporter.error(f"{label} {info.name} failed: {error}")
            view.showStatus(f"{label} failed: {error}")
            return
        view.showStatus(f"{label} handed to the plugin manager.")

    def refreshStates(self, view: SearchWindowView, info: PluginInfo | None, availableVersion: str) -> None:
        """Ask the manager which actions apply to the current selection."""
        if info is None:
            view.setActionStates(ActionStates())
            return
        try:
            states = self.gateway.actionStates(info.name, availableVersion)
        except Exception as error:  # noqa: BLE001 - conservative fallback
            self.reporter.warn(f"Plugin manager state unavailable: {error}")
            states = ActionStates()
        view.setActionStates(states)

# @impl 0f87-6ae3-6985-0cec
# @impl 0f87-6ae3-6996-c732
