"""Right panel: two tabs, Metadata first (default) and Readme."""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QTabWidget, QWidget

from ..Domain.Entities import PluginInfo
from .MetadataPanel import MetadataPanel
from .ReadmeView import ReadmeView

METADATA_TAB_INDEX = 0
README_TAB_INDEX = 1


class DetailsPanel(QTabWidget):
    """Shows the metadata of the selection and its readme when it arrives."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.metadataPanel = MetadataPanel(self)
        self.readmeView = ReadmeView(self)
        self.addTab(self.metadataPanel, self.tr("Metadata"))
        self.addTab(self.readmeView, self.tr("Readme"))
        self.setCurrentIndex(METADATA_TAB_INDEX)

    def showMetadata(self, info: PluginInfo) -> None:
        self.metadataPanel.showPlugin(info)

    def showReadme(self, pluginId: int, text: str) -> None:
        self.readmeView.showText(text)

    def showReadmePlaceholder(self, pluginId: int, message: str) -> None:
        self.readmeView.showPlaceholder(message)

    def clearDetails(self) -> None:
        self.metadataPanel.showPlugin(
            PluginInfo(pluginId=0, name="", description="")
        )
        self.readmeView.showPlaceholder("")
