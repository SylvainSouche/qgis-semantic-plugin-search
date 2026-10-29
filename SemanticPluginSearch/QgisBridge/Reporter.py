"""User reporting through the QGIS message bar."""
from __future__ import annotations

from qgis.core import Qgis
from qgis.gui import QgisInterface

from ..Domain.Ports import Reporter


class MessageBarReporter(Reporter):
    """Shows messages in the QGIS message bar with sensible durations."""

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface

    def info(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            "Semantic Plugin Search", message, level=Qgis.Info, duration=4
        )

    def warn(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            "Semantic Plugin Search", message, level=Qgis.Warning, duration=6
        )

    def error(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            "Semantic Plugin Search", message, level=Qgis.Critical, duration=8
        )
