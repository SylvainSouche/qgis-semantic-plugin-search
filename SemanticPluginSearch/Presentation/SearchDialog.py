"""The semantic search window.

Layout: query box on top, filter toggles and a result count under it,
results list on the left, details panel on the right (two tabs), action
buttons and a muted status line at the bottom. The window implements the
SearchWindowView protocol structurally; all behavior lives in the
controllers it forwards to. Geometry, splitter layout and the visibility
toggles are persisted per profile.
"""
from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QSettings, Qt, QTimer, QSize
from qgis.PyQt.QtGui import QFont, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
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
from ..QgisBridge.Settings import (
    UI_GEOMETRY,
    UI_INCLUDE_DEPRECATED,
    UI_INCLUDE_EXPERIMENTAL,
    UI_SPLITTER,
)
from .DetailsPanel import DetailsPanel

ACTION_LABELS = (
    ("install", "Install"),
    ("upgrade", "Upgrade"),
    ("reinstall", "Reinstall"),
    ("uninstall", "Uninstall"),
)
LIVE_SEARCH_DELAY_MS = 300
DESCRIPTION_EXCERPT_CHARS = 110
ICON_SIZE = 32
SCORE_COLUMN_WIDTH = 56
ROW_MIN_HEIGHT = 40


class SearchDialog(QDialog):
    """Two pane search window; the controllers are injected as a bundle."""

    def __init__(self, controllers, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.controllers = controllers
        self.results: list[SearchResult] = []
        self._iconLabels: dict[int, QLabel] = {}
        self.setWindowTitle(self.tr("Semantic Plugin Search"))
        self.setWindowIcon(self._pluginIcon())
        self._buildUi()
        self._restoreState()
        self._wire()

    @staticmethod
    def _pluginIcon():  # noqa: ANN202
        iconPath = Path(__file__).resolve().parents[1] / "assets" / "Icon.svg"
        return QIcon(str(iconPath)) if iconPath.is_file() else QIcon()

    # ------------------------------------------------------------------ UI

    def _buildUi(self) -> None:
        self.queryEdit = QLineEdit(self)
        self.queryEdit.setClearButtonEnabled(True)
        self.queryEdit.setPlaceholderText(
            self.tr("Describe what you are looking for, e.g. classify a drone orthophoto")
        )
        self.searchButton = QPushButton(self.tr("Search"), self)
        self.searchButton.setDefault(True)

        self.experimentalBox = QCheckBox(self.tr("Include experimental"), self)
        self.experimentalBox.setToolTip(
            self.tr("Experimental plugins are excluded unless this is checked.")
        )
        self.deprecatedBox = QCheckBox(self.tr("Include deprecated"), self)
        self.deprecatedBox.setToolTip(
            self.tr("Deprecated plugins are excluded unless this is checked.")
        )
        self.countLabel = QLabel("", self)

        self.resultsList = QListWidget(self)
        self.resultsList.setUniformItemSizes(False)
        self.detailsPanel = DetailsPanel(self)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self.resultsList)
        self.splitter.addWidget(self.detailsPanel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        self.actionButtons: dict[str, QPushButton] = {}
        actionsRow = QHBoxLayout()
        actionsRow.addStretch(1)
        for action, label in ACTION_LABELS:
            button = QPushButton(self.tr(label), self)
            button.setEnabled(False)
            self.actionButtons[action] = button
            actionsRow.addWidget(button)

        self.statusLabel = QLabel(self)
        self.statusLabel.setStyleSheet("color: palette(mid);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(8)
        queryRow = QHBoxLayout()
        queryRow.setSpacing(6)
        queryRow.addWidget(self.queryEdit, 1)
        queryRow.addWidget(self.searchButton)
        layout.addLayout(queryRow)
        filterRow = QHBoxLayout()
        filterRow.setSpacing(12)
        filterRow.addWidget(self.experimentalBox)
        filterRow.addWidget(self.deprecatedBox)
        filterRow.addStretch(1)
        filterRow.addWidget(self.countLabel)
        layout.addLayout(filterRow)
        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.statusLabel)
        layout.addLayout(actionsRow)

        self.liveSearchTimer = QTimer(self)
        self.liveSearchTimer.setSingleShot(True)
        self.liveSearchTimer.setInterval(LIVE_SEARCH_DELAY_MS)

    def _wire(self) -> None:
        self.searchButton.clicked.connect(self._onSearchRequested)
        self.queryEdit.returnPressed.connect(self._onSearchRequested)
        self.queryEdit.textEdited.connect(self._onQueryEdited)
        self.liveSearchTimer.timeout.connect(self._onSearchRequested)
        self.experimentalBox.toggled.connect(self._onFilterChanged)
        self.deprecatedBox.toggled.connect(self._onFilterChanged)
        self.resultsList.currentItemChanged.connect(self._onSelectionChanged)
        for action, button in self.actionButtons.items():
            button.clicked.connect(lambda _=False, a=action: self._onAction(a))

    # ------------------------------------------------------- Qt callbacks

    def _onQueryEdited(self, _text: str) -> None:
        self.liveSearchTimer.start()

    def _onSearchRequested(self) -> None:
        self.liveSearchTimer.stop()
        self.controllers.search.search(self, self.queryEdit.text())

    def _onFilterChanged(self, _checked: bool) -> None:
        settings = QSettings()
        settings.setValue(UI_INCLUDE_EXPERIMENTAL, self.experimentalBox.isChecked())
        settings.setValue(UI_INCLUDE_DEPRECATED, self.deprecatedBox.isChecked())
        self.controllers.search.setFilters(
            self.experimentalBox.isChecked(), self.deprecatedBox.isChecked()
        )
        self._onSearchRequested()

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

    # --------------------------------------------------- persisted state

    def _restoreState(self) -> None:
        settings = QSettings()
        experimental = settings.value(UI_INCLUDE_EXPERIMENTAL, False, type=bool)
        deprecated = settings.value(UI_INCLUDE_DEPRECATED, False, type=bool)
        self.experimentalBox.setChecked(experimental)
        self.deprecatedBox.setChecked(deprecated)
        self.controllers.search.setFilters(experimental, deprecated)
        geometry = settings.value(UI_GEOMETRY)
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitterState = settings.value(UI_SPLITTER)
        if splitterState is not None:
            self.splitter.restoreState(splitterState)

    def _persistState(self) -> None:
        settings = QSettings()
        settings.setValue(UI_GEOMETRY, self.saveGeometry())
        settings.setValue(UI_SPLITTER, self.splitter.saveState())

    def closeEvent(self, event) -> None:  # noqa: ANN001 - QCloseEvent
        self._persistState()
        super().closeEvent(event)

    # ------------------------------------- SearchWindowView protocol side

    def showResults(self, results: list[SearchResult]) -> None:
        self.results = list(results)
        self._iconLabels.clear()
        self.resultsList.blockSignals(True)
        self.resultsList.clear()
        for result in self.results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, result.info.pluginId)
            item.setToolTip(result.info.description)
            self.resultsList.addItem(item)
            row = self._buildRow(result)
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self.resultsList.setItemWidget(item, row)
        self.resultsList.blockSignals(False)
        self.countLabel.setText(self.tr("{} plugin(s)").format(len(self.results)))
        self.controllers.icons.fetchFor(self.results, self._showIcon)
        if self.results:
            # Default the details to the first result when nothing is selected.
            self.resultsList.setCurrentRow(0)
        else:
            self.detailsPanel.clearDetails()
            self.setActionStates(ActionStates())

    # ------------------------------------------------------ result rows

    def _buildRow(self, result: SearchResult) -> QWidget:
        """One row: icon, bold title over smaller serif description, and the
        similarity percentage in a right aligned column aligned with the
        title line, two pixels from the icon."""
        row = QWidget(self.resultsList)
        row.setMinimumHeight(ROW_MIN_HEIGHT)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        iconLabel = QLabel(row)
        iconLabel.setFixedSize(ICON_SIZE, ICON_SIZE)
        self._iconLabels[result.info.pluginId] = iconLabel
        layout.addWidget(iconLabel)

        textColumn = QVBoxLayout()
        textColumn.setSpacing(0)
        nameLabel = QLabel(result.info.name, row)
        nameFont = nameLabel.font()
        nameFont.setBold(True)
        nameLabel.setFont(nameFont)
        descriptionLabel = QLabel(self._excerpt(result.info.description), row)
        descriptionFont = QFont("Times New Roman")
        descriptionFont.setStyleHint(QFont.StyleHint.Serif)
        descriptionFont.setPointSize(max(9, nameFont.pointSize() - 2))
        descriptionLabel.setFont(descriptionFont)
        textColumn.addWidget(nameLabel)
        textColumn.addWidget(descriptionLabel)
        layout.addLayout(textColumn, 1)

        flags = []
        if result.info.experimental:
            flags.append("exp")
        if result.info.deprecated:
            flags.append("dep")
        scoreLabel = QLabel(
            self.tr("{percent}%{flags}").format(
                percent=f"{result.score * 100:.0f}",
                flags=f"  [{' / '.join(flags)}]" if flags else "",
            ),
            row,
        )
        scoreFont = scoreLabel.font()
        scoreFont.setBold(True)
        scoreLabel.setFont(scoreFont)
        scoreLabel.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        scoreLabel.setFixedWidth(SCORE_COLUMN_WIDTH)
        layout.addWidget(scoreLabel)
        return row

    @staticmethod
    def _excerpt(description: str) -> str:
        text = description.replace("\n", " ").strip()
        if len(text) > DESCRIPTION_EXCERPT_CHARS:
            text = text[:DESCRIPTION_EXCERPT_CHARS].rstrip() + "…"
        return text

    def _showIcon(self, pluginId: int, payload: bytes) -> None:
        """Icon bytes arrived from the background fetch; replace the slot."""
        label = self._iconLabels.get(pluginId)
        if label is None:
            return  # the rows were rebuilt since the fetch started
        pixmap = QPixmap()
        if pixmap.loadFromData(payload):
            label.setPixmap(
                pixmap.scaled(
                    ICON_SIZE,
                    ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

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

# @impl 0f87-6ae3-a1e6-0cd7

# @impl 0f87-6ae3-6985-53e9

# @impl 0f87-6ae3-ab0f-ea79
