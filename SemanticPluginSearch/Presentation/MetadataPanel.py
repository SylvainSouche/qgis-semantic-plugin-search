"""Metadata form of the right panel."""
from __future__ import annotations

from html import escape
from urllib.parse import urlparse


from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QFormLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..Domain.Entities import PluginInfo


class MetadataPanel(QWidget):
    """Read only presentation of one plugin metadata snapshot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nameLabel = QLabel(self)
        self.nameLabel.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.nameLabel.setWordWrap(True)
        self.versionLabel = QLabel(self)
        self.authorLabel = QLabel(self)
        self.descriptionLabel = QLabel(self)
        self.descriptionLabel.setWordWrap(True)
        self.aboutView = QTextBrowser(self)
        self.aboutView.setOpenExternalLinks(False)
        self.tagsLabel = QLabel(self)
        self.tagsLabel.setWordWrap(True)
        self.statsLabel = QLabel(self)
        self.aboutCaption = QLabel(self.tr("About:"))
        self.linksView = QTextBrowser(self)
        self.linksView.setOpenLinks(False)
        self.linksView.setOpenExternalLinks(False)
        self.linksView.anchorClicked.connect(self._openLink)
        self.linksView.setMaximumHeight(70)

        form = QFormLayout()
        form.addRow(self.tr("Version:"), self.versionLabel)
        form.addRow(self.tr("Author:"), self.authorLabel)
        form.addRow(self.tr("Tags:"), self.tagsLabel)
        form.addRow(self.tr("Stats:"), self.statsLabel)
        form.addRow(self.tr("Links:"), self.linksView)

        layout = QVBoxLayout(self)
        layout.addWidget(self.nameLabel)
        layout.addWidget(self.descriptionLabel)
        layout.addLayout(form)
        layout.addWidget(self.aboutCaption)
        layout.addWidget(self.aboutView, 1)

    def showPlugin(self, info: PluginInfo) -> None:
        self.nameLabel.setText(info.name)
        self.versionLabel.setText(
            self._versionText(info)
        )
        self.authorLabel.setText(info.author)
        self.descriptionLabel.setText(info.description)
        self.aboutView.setPlainText(info.about or info.description)
        self.tagsLabel.setText(info.tagText())
        self.statsLabel.setText(self._statsText(info))
        self.linksView.setHtml(self._linksHtml(info))

    @staticmethod
    def _versionText(info: PluginInfo) -> str:
        flags = []
        if info.experimental:
            flags.append("experimental")
        if info.deprecated:
            flags.append("deprecated")
        suffix = f" ({', '.join(flags)})" if flags else ""
        compatibility = ""
        if info.qgisMinimum or info.qgisMaximum:
            compatibility = f" — QGIS {info.qgisMinimum} to {info.qgisMaximum}"
        return f"{info.version}{suffix}{compatibility}"

    @staticmethod
    def _statsText(info: PluginInfo) -> str:
        vote = f", rating {info.averageVote:.1f}" if info.votes else ""
        return f"{info.downloads} downloads{vote}"

    @staticmethod
    def _link(label: str, url: str) -> str:
        """An escaped link, only for web schemes the OS should open."""
        if urlparse(url).scheme.lower() not in ("http", "https"):
            return ""
        return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'

    def _openLink(self, url) -> None:  # noqa: ANN001 - QUrl
        """Only web schemes reach the OS; catalogue text is not trusted."""
        if url.scheme().lower() in ("http", "https"):
            QDesktopServices.openUrl(url)

    @classmethod
    def _linksHtml(cls, info: PluginInfo) -> str:
        links = [
            link
            for link in (
                cls._link("Homepage", info.homepage),
                cls._link("Repository", info.repository),
                cls._link("Tracker", info.tracker),
                cls._link("Download", info.downloadUrl),
            )
            if link
        ]
        return " · ".join(links) or "—"
