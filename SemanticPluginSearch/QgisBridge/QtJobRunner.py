"""Background job execution marshaled back to the Qt main loop.

QThreadPool runs the task; completion is signaled through a QObject that
lives on the GUI thread and is connected queued, so the
controller callbacks always run on the GUI thread even though the signal is
emitted from a worker thread. Each job carries its own callbacks through the
signal payload, so overlapping jobs cannot dispatch to each other's handlers.
"""
from __future__ import annotations

from collections.abc import Callable

from qgis.PyQt.QtCore import QObject, Qt, QRunnable, QThreadPool, pyqtSignal

from ..Domain.Ports import JobRunner


class _Task(QRunnable):
    def __init__(
        self,
        work: Callable,
        on_success: Callable,
        on_failure: Callable,
        runner: "QtJobRunner",
    ) -> None:
        super().__init__()
        self.work = work
        self.on_success = on_success
        self.on_failure = on_failure
        self.runner = runner

    def run(self) -> None:  # noqa: D102 - QRunnable API
        try:
            result = self.work()
        except Exception as error:  # noqa: BLE001 - marshaled to the caller
            self.runner.failed.emit((self.on_failure, error))
        else:
            self.runner.succeeded.emit((self.on_success, result))


class QtJobRunner(QObject):
    """Runs jobs on the global thread pool, results back on the GUI thread."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self.succeeded.connect(self._dispatchSuccess, Qt.ConnectionType.QueuedConnection)
        self.failed.connect(self._dispatchFailure, Qt.ConnectionType.QueuedConnection)

    def submit(
        self,
        task: Callable,
        on_success: Callable,
        on_failure: Callable,
    ) -> None:
        self._pool.start(_Task(task, on_success, on_failure, self))

    def _dispatchSuccess(self, message: tuple) -> None:
        callback, result = message
        callback(result)

    def _dispatchFailure(self, message: tuple) -> None:
        callback, error = message
        callback(error)
