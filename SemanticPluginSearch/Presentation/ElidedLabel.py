"""A one line label that ends with an ellipsis when its text does not fit."""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """Shows as much of its text as fits, ending with "…", never wider than
    the space it is given (it does not ask the layout for its full width)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fullText = text
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(1)
        self._elide()

    def fullText(self) -> str:
        return self._fullText

    def resizeEvent(self, event) -> None:  # noqa: ANN001 - QResizeEvent
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(self.width(), 1)
        super().setText(
            self.fontMetrics().elidedText(self._fullText, Qt.TextElideMode.ElideRight, width)
        )
# @impl 4be9-6ae4-4521-3222
