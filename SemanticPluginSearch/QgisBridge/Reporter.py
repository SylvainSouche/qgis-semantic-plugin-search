"""User reporting through the QGIS message bar, and a popup for every error.

Errors must never hide in the message bar or the log panel: each one also
opens a dialog. The dialog is non modal (show, not exec), so several errors
never stack nested event loops, and it is parented to the active window so
it appears above the search window when that is in front.

The reporter is called from worker threads (the asset refresh runs in the
thread pool), and widgets may only be touched from the GUI thread: pushing
a message from a pool thread crashes QGIS on macOS. Every message is
therefore marshaled to the GUI thread through a queued signal.

The QObject lives in an internal bridge: PyQt's sip metaclass and the ABC
metaclass of the Reporter port cannot be combined in one class statement.
"""
from __future__ import annotations

from qgis.core import Qgis
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from ..Domain.Ports import Reporter

TITLE = "Semantic Plugin Search"


class _MessageBarBridge(QObject):
    """Owns the signals and pushes on whatever thread it lives on (GUI)."""

    infoRequested = pyqtSignal(str)
    warnRequested = pyqtSignal(str)
    errorRequested = pyqtSignal(str)

    def __init__(self, iface: QgisInterface) -> None:
        super().__init__()
        self.iface = iface
        self.infoRequested.connect(self._pushInfo, Qt.ConnectionType.QueuedConnection)
        self.warnRequested.connect(self._pushWarn, Qt.ConnectionType.QueuedConnection)
        self.errorRequested.connect(self._pushError, Qt.ConnectionType.QueuedConnection)

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
        self._popup(message)

    def _popup(self, message: str) -> None:
        parent = QApplication.activeWindow() or self.iface.mainWindow()
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(TITLE)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.show()


class MessageBarReporter(Reporter):
    """Thread safe reporter: emit here, push on the GUI thread."""

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self._bridge = _MessageBarBridge(iface)

    def info(self, message: str) -> None:
        self._bridge.infoRequested.emit(message)

    def warn(self, message: str) -> None:
        self._bridge.warnRequested.emit(message)

    def error(self, message: str) -> None:
        self._bridge.errorRequested.emit(message)


Reporter.register(MessageBarReporter)
# @impl 4be9-6ae4-4c75-c7ae
