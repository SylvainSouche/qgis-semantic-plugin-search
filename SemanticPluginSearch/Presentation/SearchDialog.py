"""The semantic search window.

Layout: query box on top, results list on the left, details panel on the
right (two tabs), action buttons and a status line at the bottom. The window
implements the SearchWindowView protocol structurally; all behavior lives in
the controllers it forwards to.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..Domain.Entities import ActionStates, PluginInfo, SearchResult
from .DetailsPanel import DetailsPanel

ACTION_LABELS = (
    ("install", "Install"),
    ("upgrade", "Upgrade"),
    ("reinstall", "Reinstall"),
    ("uninstall", "Uninstall"),
)


class SearchDialog(QDialog):
    """Two pane search window; the controllers are injected as a bundle."""

    def __init__(self, controllers, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.controllers = controllers
        self.results: list[SearchResult] = []
        self.setWindowTitle(self.tr("Semantic Plugin Search"))
        self.resize(920, 620)
        self._buildUi()
        self._wire()

    # ------------------------------------------------------------------ UI

    def _buildUi(self) -> None:
        self.queryEdit = QLineEdit(self)
        self.queryEdit.setPlaceholderText(
            self.tr("Describe what you are looking for, e.g. classify a drone orthophoto")
        )
        self.searchButton = QPushButton(self.tr("Search"), self)

        self.resultsList = QListWidget(self)
        self.detailsPanel = DetailsPanel(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.resultsList)
        splitter.addWidget(self.detailsPanel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.actionButtons: dict[str, QPushButton] = {}
        actionsRow = QHBoxLayout()
        for action, label in ACTION_LABELS:
            button = QPushButton(self.tr(label), self)
            button.setEnabled(False)
            self.actionButtons[action] = button
            actionsRow.addWidget(button)
        actionsRow.addStretch(1)

        self.statusLabel = QLabel(self)

        layout = QVBoxLayout(self)
        queryRow = QHBoxLayout()
        queryRow.addWidget(self.queryEdit, 1)
        queryRow.addWidget(self.searchButton)
        layout.addLayout(queryRow)
        layout.addWidget(splitter, 1)
        layout.addLayout(actionsRow)
        layout.addWidget(self.statusLabel)

    def _wire(self) -> None:
        self.searchButton.clicked.connect(self._onSearchRequested)
        self.queryEdit.returnPressed.connect(self._onSearchRequested)
        self.resultsList.currentItemChanged.connect(self._onSelectionChanged)
        for action, button in self.actionButtons.items():
            button.clicked.connect(lambda _=False, a=action: self._onAction(a))

    # ------------------------------------------------------- Qt callbacks

    def _onSearchRequested(self) -> None:
        self.controllers.search.search(self, self.queryEdit.text())

    def _onSelectionChanged(self, current: QListWidgetItem | None, _previous=None) -> None:  # noqa: ANN001
        if current is None:
            self.controllers.details.showDetails(self, self._infoOf(None))
            return
        info = self._infoOf(current.data(Qt.ItemDataRole.UserRole))
        if info is not None:
            self.controllers.details.showDetails(self, info)
            self.controllers.actions.refreshStates(self, info, info.version)

    def _onAction(self, action: str) -> None:
        item = self.resultsList.currentItem()
        info = self._infoOf(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None
        self.controllers.actions.runAction(self, action, info)

    def _infoOf(self, pluginId: int | None) -> PluginInfo | None:
        if pluginId is None:
            return None
        for result in self.results:
            if result.info.pluginId == pluginId:
                return result.info
        return None

    # ------------------------------------- SearchWindowView protocol side

    def showResults(self, results: list[SearchResult]) -> None:
        self.results = list(results)
        self.resultsList.blockSignals(True)
        self.resultsList.clear()
        for result in self.results:
            item = QListWidgetItem(f"{result.info.name}  ({result.score * 100:.0f}%)")
            item.setData(Qt.ItemDataRole.UserRole, result.info.pluginId)
            item.setToolTip(result.info.description)
            self.resultsList.addItem(item)
        self.resultsList.blockSignals(False)
        if self.results:
            # Default the details to the first result when nothing is selected.
            self.resultsList.setCurrentRow(0)
        else:
            self.detailsPanel.clearDetails()
            self.setActionStates(ActionStates())

    def showStatus(self, message: str) -> None:
        self.statusLabel.setText(message)

    def showMetadata(self, info: PluginInfo) -> None:
        self.detailsPanel.showMetadata(info)

    def showReadme(self, pluginId: int, text: str) -> None:
        self.detailsPanel.showReadme(pluginId, text)

    def showReadmePlaceholder(self, pluginId: int, message: str) -> None:
        self.detailsPanel.showReadmePlaceholder(pluginId, message)

    def setActionStates(self, states: ActionStates) -> None:
        self.actionButtons["install"].setEnabled(states.canInstall)
        self.actionButtons["upgrade"].setEnabled(states.canUpgrade)
        self.actionButtons["reinstall"].setEnabled(states.canReinstall)
        self.actionButtons["uninstall"].setEnabled(states.canUninstall)
        if states.installedVersion:
            self.actionButtons["uninstall"].setToolTip(
                self.tr("Installed version: {version}").format(
                    version=states.installedVersion
                )
            )

    def clearDetails(self) -> None:
        self.detailsPanel.clearDetails()

# @impl 0f87-6ae3-6985-53e9
