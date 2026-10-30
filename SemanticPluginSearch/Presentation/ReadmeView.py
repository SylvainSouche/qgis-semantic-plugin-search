"""Readme display of the right panel."""
from __future__ import annotations

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QTextBrowser, QVBoxLayout, QWidget


class ReadmeView(QWidget):
    """Renders a plugin readme, markdown first, plain text as fallback.

    Links never navigate inside the view and only http(s) URLs reach the
    OS: catalogue text is author supplied, not trusted.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.browser = QTextBrowser(self)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._openLink)
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

    def _openLink(self, url: QUrl) -> None:
        if url.scheme().lower() in ("http", "https"):
            QDesktopServices.openUrl(url)
