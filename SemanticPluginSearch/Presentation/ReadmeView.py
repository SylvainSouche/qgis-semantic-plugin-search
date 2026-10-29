"""Readme display of the right panel."""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QTextBrowser, QVBoxLayout, QWidget


class ReadmeView(QWidget):
    """Renders a plugin readme, markdown first, plain text as fallback."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)

    def showPlaceholder(self, message: str) -> None:
        self.browser.setPlainText(message)

    def showText(self, text: str) -> None:
        try:
            self.browser.setMarkdown(text)
        except (AttributeError, RuntimeError):
            # Qt builds without markdown support: render plain text.
            self.browser.setPlainText(text)

    def showHtml(self, html: str) -> None:
        self.browser.setHtml(html)
