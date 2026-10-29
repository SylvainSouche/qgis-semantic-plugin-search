"""Plugin lifecycle: wiring of adapters, controllers and window.

This module is the composition root: it builds the QGIS adapters, the
controllers and the window, and owns nothing else.
"""
from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QAction

try:  # QAction lives in QtGui on PyQt6 (QGIS 4) and QtWidgets on PyQt5 (QGIS 3).
    from qgis.PyQt.QtGui import QAction  # noqa: F811
except ImportError:  # pragma: no cover - QGIS 3 / PyQt5
    pass

from .Controllers.ActionController import ActionController
from .Controllers.AssetsController import AssetsController
from .Controllers.DetailsController import DetailsController
from .Controllers.IconController import IconController
from .Controllers.SearchController import SearchController
from .Data.AssetGateways import HttpAssetGateway, HttpIconGateway, HttpReadmeGateway
from .Data.DeferredEmbeddingEngine import DeferredEmbeddingEngine
from .Domain.SearchEngine import SearchService
from .QgisBridge import (
    MessageBarReporter,
    PluginInstallerGateway,
    ProfilePathsProvider,
    QgisVersionProvider,
    QtJobRunner,
    configuredIndexUrl,
)


class Controllers(QObject):
    """Bundle of controllers handed to the window."""

    def __init__(self, search, details, actions, assets, icons) -> None:  # noqa: ANN001
        super().__init__()
        self.search = search
        self.details = details
        self.actions = actions
        self.assets = assets
        self.icons = icons


class SemanticPluginSearchPlugin:
    """Standard QGIS plugin object; owns menu entry and window."""

    def __init__(self, iface) -> None:  # noqa: ANN001 - QgisInterface
        self.iface = iface
        self.engine = None
        self.action: QAction | None = None
        self.dialog = None  # SearchDialog, created on first open
        self.controllers: Controllers | None = None

    def initGui(self) -> None:
        iconPath = Path(__file__).parent / "assets" / "Icon.svg"
        self.action = QAction(
            "Semantic Plugin Search", self.iface.mainWindow()
        )
        self.action.setIcon(self._icon(iconPath))
        self.action.setObjectName("SemanticPluginSearchAction")
        self.action.triggered.connect(self.openDialog)
        self.iface.addPluginToMenu("&Semantic Plugin Search", self.action)
        self.iface.addToolBarIcon(self.action)

    @staticmethod
    def _icon(iconPath: Path):
        from qgis.PyQt.QtGui import QIcon

        return QIcon(str(iconPath))

    def unload(self) -> None:
        if self.action is not None:
            self.iface.removePluginMenu("&Semantic Plugin Search", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def openDialog(self) -> None:
        if self.dialog is None:
            self.controllers = self._buildControllers()
            from .Presentation.SearchDialog import SearchDialog

            self.dialog = SearchDialog(self.controllers)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        # Refresh assets in the background on every open.
        self.controllers.assets.refresh()

    def _buildControllers(self) -> Controllers:
        reporter = MessageBarReporter(self.iface)
        paths = ProfilePathsProvider()
        versionProvider = QgisVersionProvider()
        runner = QtJobRunner()
        gateway = HttpAssetGateway(indexUrl=configuredIndexUrl())
        readmeGateway = HttpReadmeGateway()
        actionsGateway = PluginInstallerGateway(self.iface, reporter)
        engine = DeferredEmbeddingEngine(paths)
        self.engine = engine

        searchController = SearchController(
            engine=engine,
            searchService=SearchService(engine),
            reporter=reporter,
        )
        detailsController = DetailsController(readmeGateway, runner)
        actionController = ActionController(actionsGateway, reporter)
        assetsController = AssetsController(
            gateway=gateway,
            paths=paths,
            versionProvider=versionProvider,
            runner=runner,
            reporter=reporter,
            onStoreReady=self._onStoreReady,
        )
        iconController = IconController(
            HttpIconGateway(paths.cacheDir() / "Icons"), runner
        )
        return Controllers(
            searchController,
            detailsController,
            actionController,
            assetsController,
            iconController,
        )

    def _onStoreReady(self, store) -> None:  # noqa: ANN001
        if self.controllers is None or self.dialog is None:
            return
        if self.engine is not None:
            # Size placeholder embeddings to the database before it is usable.
            self.engine.setExpectedDimension(store.modelDim())
        self.controllers.search.setStore(store)
        # Re-run the current query against the fresh store.
        self.controllers.search.search(self.dialog, self.dialog.queryEdit.text())
