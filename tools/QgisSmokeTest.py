"""Smoke test inside real QGIS: boots QgsApplication offscreen and exercises
the plugin with the genuine qgis and PyQt modules of the installed QGIS.

This is the layer the offline pytest suite cannot reach: PluginEntry,
Presentation and QgisBridge only import where qgis and Qt exist, and their
failures until now surfaced only inside QGIS.

Run with QGIS's bundled interpreter, e.g. on macOS:
  QT_QPA_PLATFORM=offscreen \
    /Applications/QGIS-final-4_2_3.app/Contents/MacOS/python3.12 \
    tools/QgisSmokeTest.py

Exit code 0 means the plugin imports, constructs, reports and searches
inside real QGIS.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from qgis.core import QgsApplication  # noqa: E402

checks: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    checks.append(f"{'OK  ' if condition else 'FAIL'} {label}{' — ' + detail if detail else ''}")
    if not condition:
        raise AssertionError(f"smoke check failed: {label} {detail}")


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QgsApplication([], True)
    app.initQgis()

    from qgis.gui import QgsMessageBar

    # 1. The composition root imports under real qgis/PyQt.
    from SemanticPluginSearch import PluginEntry  # noqa: F401
    from SemanticPluginSearch.Presentation import SearchDialog
    from SemanticPluginSearch.QgisBridge import (
        MessageBarReporter,
        ProfilePathsProvider,
        QgisVersionProvider,
        QtJobRunner,
    )
    check("plugin imports under real QGIS", True)

    # 2. Version provider maps this running QGIS onto a universe.
    versionProvider = QgisVersionProvider()
    universe = versionProvider.universe()
    check("version provider resolves universe", universe in ("3", "4"), f"universe={universe}")

    # 3. The reporter pushes through a real QgsMessageBar; the queued signal
    #    needs an event loop turn to deliver.
    messageBar = QgsMessageBar()
    pushed: list[tuple[str, int]] = []
    originalPush = messageBar.pushMessage

    def spyPush(title, text, level=None, duration=5, **kwargs):  # noqa: ANN001
        pushed.append((text, int(level) if level is not None else -1))
        return originalPush(title, text, level=level, duration=duration, **kwargs)

    messageBar.pushMessage = spyPush

    class FakeIface:
        def messageBar(self):  # noqa: ANN202
            return messageBar

        def mainWindow(self):  # noqa: ANN202
            return None

        def addPluginToMenu(self, *args):  # noqa: ANN002, ANN202
            pass

        def removePluginMenu(self, *args):  # noqa: ANN002, ANN202
            pass

        def addToolBarIcon(self, *args):  # noqa: ANN002, ANN202
            pass

        def removeToolBarIcon(self, *args):  # noqa: ANN002, ANN202
            pass

    reporter = MessageBarReporter(FakeIface())
    reporter.info("smoke info")
    reporter.error("smoke error")
    app.processEvents()
    app.processEvents()
    check("queued reporting reached the real message bar", len(pushed) == 2, f"pushed={pushed}")

    # 4. The window builds against real widgets with real controllers wired
    #    to a temporary profile.
    class FakeReporter:
        def __init__(self):  # noqa: ANN204
            self.messages = []
        def info(self, message):  # noqa: ANN001, ANN202
            self.messages.append(("info", message))
        def warn(self, message):  # noqa: ANN001, ANN202
            self.messages.append(("warn", message))
        def error(self, message):  # noqa: ANN001, ANN202
            self.messages.append(("error", message))

    class InlineRunner:
        def submit(self, task, on_success, on_failure):  # noqa: ANN001, ANN202
            try:
                on_success(task())
            except Exception as error:  # noqa: BLE001
                on_failure(error)

    from SemanticPluginSearch.Controllers.ActionController import ActionController
    from SemanticPluginSearch.Controllers.AssetsController import AssetsController
    from SemanticPluginSearch.Controllers.DetailsController import DetailsController
    from SemanticPluginSearch.Controllers.SearchController import SearchController
    from SemanticPluginSearch.Data.AssetGateways import HttpAssetGateway, HttpReadmeGateway
    from SemanticPluginSearch.Domain.SearchEngine import SearchService
    from SemanticPluginSearch.PluginEntry import Controllers, DeferredEmbeddingEngine

    class FakeGateway:
        def fetchIndex(self):  # noqa: ANN202
            raise RuntimeError("smoke test: no index fetch")

        def downloadVerified(self, remoteFile, destination):  # noqa: ANN002, ANN202
            raise RuntimeError("smoke test: no downloads")

    class FakeManagerGateway:
        def install(self, pluginName):  # noqa: ANN002, ANN202
            self.last = ("install", pluginName)

        def upgrade(self, pluginName):  # noqa: ANN002, ANN202
            self.last = ("upgrade", pluginName)

        def reinstall(self, pluginName):  # noqa: ANN002, ANN202
            self.last = ("reinstall", pluginName)

        def uninstall(self, pluginName):  # noqa: ANN002, ANN202
            self.last = ("uninstall", pluginName)

        def actionStates(self, pluginName, availableVersion):  # noqa: ANN002, ANN202
            from SemanticPluginSearch.Domain.Entities import ActionStates

            return ActionStates(canInstall=True)

    tmpProfile = Path(tempfile.mkdtemp(prefix="smoke-profile-"))
    paths = ProfilePathsProvider(rootDir=tmpProfile)
    runner = InlineRunner()
    readmeGateway = HttpReadmeGateway()
    managerGateway = FakeManagerGateway()
    engine = DeferredEmbeddingEngine(paths)
    searchController = SearchController(engine, SearchService(engine), FakeReporter())
    detailsController = DetailsController(readmeGateway, runner)
    actionController = ActionController(managerGateway, FakeReporter())

    def onStoreReady(store):  # noqa: ANN001, ANN202
        pass

    assetsController = AssetsController(
        gateway=FakeGateway(),
        paths=paths,
        versionProvider=versionProvider,
        runner=runner,
        reporter=FakeReporter(),
        onStoreReady=onStoreReady,
    )
    controllers = Controllers(searchController, detailsController, actionController, assetsController)

    dialog = SearchDialog(controllers)
    dialog.resize(920, 620)
    check("search window builds with real widgets", True)

    # 5. The no-store search path drives the real view end to end.
    searchController.search(dialog, "classify a drone orthophoto")
    check("search without store reports gracefully", bool(dialog.statusLabel.text()))
    check("no results shown", dialog.resultsList.count() == 0)

    # 6. Action buttons route through the gateway.
    actionController.runAction(dialog, "install", None)
    check("action without selection is ignored", managerGateway.__dict__.get("last") is None)

    # 7. The asset refresh fails safely against the fake gateway (no crash,
    #    the failure surfaces through the reporter, not the process).
    assetsController.refresh()
    app.processEvents()
    app.processEvents()
    check("asset refresh fails safely", True)

    app.exitQgis()
    for line in checks:
        print(line)
    print(f"QGIS smoke test passed ({len(checks)} checks, "
          f"QGIS {versionProvider.qgisVersion()}, universe {universe})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
