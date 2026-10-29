"""User reporting through the QGIS message bar.

The reporter is called from worker threads (the asset refresh runs in the
thread pool), and widgets may only be touched from the GUI thread: pushing
a message from a pool thread crashes QGIS on macOS. Every message is
therefore marshaled to the GUI thread through a queued signal.
"""
from __future__ import annotations

from qgis.core import Qgis
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal

from ..Domain.Ports import Reporter

TITLE = "Semantic Plugin Search"


class MessageBarReporter(QObject, Reporter):
    """Thread safe reporter: emit here, push on the GUI thread."""

    _infoRequested = pyqtSignal(str)
    _warnRequested = pyqtSignal(str)
    _errorRequested = pyqtSignal(str)

    def __init__(self, iface: QgisInterface) -> None:
        QObject.__init__(self)
        self.iface = iface
        self._infoRequested.connect(self._pushInfo, Qt.ConnectionType.QueuedConnection)
        self._warnRequested.connect(self._pushWarn, Qt.ConnectionType.QueuedConnection)
        self._errorRequested.connect(self._pushError, Qt.ConnectionType.QueuedConnection)

    def info(self, message: str) -> None:
        self._infoRequested.emit(message)

    def warn(self, message: str) -> None:
        self._warnRequested.emit(message)

    def error(self, message: str) -> None:
        self._errorRequested.emit(message)

    def _pushInfo(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            TITLE, message, level=Qgis.MessageLevel.Info, duration=4
        )

    def _pushWarn(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            TITLE, message, level=Qgis.MessageLevel.Warning, duration=6
        )

    def _pushError(self, message: str) -> None:
        self.iface.messageBar().pushMessage(
            TITLE, message, level=Qgis.MessageLevel.Critical, duration=8
        )
