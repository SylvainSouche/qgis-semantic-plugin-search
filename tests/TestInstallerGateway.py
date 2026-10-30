"""Resolution of the real pyplugin_installer API per QGIS version (the
correction of the failed delegation reported on QGIS 4.2.3, whose
pyplugin_installer exposes pyplugin_installer.instance() instead of the
QGIS 3 module level installer singleton).

The minimal qgis/Qt stubs below make the QgisBridge package importable
without QGIS, so the gateway logic is testable offline.
"""

import sys
import types

if "qgis" not in sys.modules or not hasattr(sys.modules.get("qgis"), "_stubbed"):
    _qgis = types.ModuleType("qgis")
    _qgis._stubbed = True

    _core = types.ModuleType("qgis.core")

    class _Qgis:  # noqa: N801 - Qt style
        class MessageLevel:  # noqa: N801
            Info = 0
            Warning = 1
            Critical = 2

        QGIS_VERSION = "0.0.0-stub"
        QGIS_VERSION_INT = 0

    class _QgsApplication:  # noqa: N801
        @staticmethod
        def qgisSettingsDirPath() -> str:
            return "/tmp/stub-profile"

    _core.Qgis = _Qgis
    _core.QgsApplication = _QgsApplication
    _qgis.core = _core

    _qtcore = types.ModuleType("qgis.PyQt.QtCore")

    class _QObject:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

    def _pyqtSignal(*args, **kwargs):  # noqa: ANN002, ANN003
        return None

    class _Qt:  # noqa: N801
        class ConnectionType:  # noqa: N801
            QueuedConnection = 0

    class _QSettings:
        def value(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def setValue(self, *args, **kwargs) -> None:  # noqa: ANN002
            pass

    class _QRunnable:  # noqa: N801
        pass

    class _QThreadPool:  # noqa: N801
        pass

    class _QEventLoop:  # noqa: N801
        def exec(self) -> int:  # noqa: D102
            return 0

        def quit(self) -> None:  # noqa: D102
            pass

    class _QTimer:  # noqa: N801
        @staticmethod
        def singleShot(msec, callback):  # noqa: ANN001
            callback()

    _qtcore.QObject = _QObject
    _qtcore.pyqtSignal = _pyqtSignal
    _qtcore.Qt = _Qt
    _qtcore.QSettings = _QSettings
    _qtcore.QRunnable = _QRunnable
    _qtcore.QThreadPool = _QThreadPool
    _qtcore.QEventLoop = _QEventLoop
    _qtcore.QTimer = _QTimer

    _qtgui = types.ModuleType("qgis.PyQt.QtGui")

    class _QIcon:  # noqa: N801
        pass

    _qtgui.QIcon = _QIcon

    _pyqt = types.ModuleType("qgis.PyQt")
    _pyqt.QtCore = _qtcore
    _pyqt.QtGui = _qtgui
    _qgis.PyQt = _pyqt

    _gui = types.ModuleType("qgis.gui")

    class _QgisInterface:  # noqa: N801
        pass

    class _QgsMessageBar:  # noqa: N801
        pass

    _gui.QgisInterface = _QgisInterface
    _gui.QgsMessageBar = _QgsMessageBar
    _qgis.gui = _gui

    sys.modules.update(
        {
            "qgis": _qgis,
            "qgis.core": _core,
            "qgis.gui": _gui,
            "qgis.PyQt": _pyqt,
            "qgis.PyQt.QtCore": _qtcore,
            "qgis.PyQt.QtGui": _qtgui,
        }
    )

from SemanticPluginSearch.QgisBridge.PluginInstallerGateway import (  # noqa: E402
    PluginInstallerGateway,
)
from tests.conftest import FakeReporter  # noqa: E402


class FakeIface:
    def __init__(self) -> None:
        self.shown = False

    def showPluginManager(self) -> None:
        self.shown = True


def makeGateway(iface=None):  # noqa: ANN001, ANN202
    return PluginInstallerGateway(iface or FakeIface(), FakeReporter())


def installStubModule(name: str, **attributes) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def teardownStubModules():
    for name in ("pyplugin_installer", "pyplugin_installer.installer"):
        sys.modules.pop(name, None)


class Recording:
    def __init__(self) -> None:
        self.calls = []

    def installPlugin(self, key, quiet=False):  # noqa: ANN001, ANN002
        self.calls.append(("installPlugin", key))

    def uninstallPlugin(self, key, quiet=False):  # noqa: ANN001, ANN002
        self.calls.append(("uninstallPlugin", key))


class FakeEntity:
    def __init__(self, name="SomePlugin", fileName="") -> None:  # noqa: ANN001
        self.name = name
        self.fileName = fileName


class FakeRepositories:
    def __init__(self, ready: bool, known: set, pluginToServe: str = "") -> None:  # noqa: ANN001
        self.ready = ready
        self.known = known
        self.pluginToServe = pluginToServe
        self.requested = []

    def allEnabled(self):  # noqa: ANN202
        return {"official": {}, "third-party": {}}

    def fetchingInProgress(self):  # noqa: ANN202
        return not self.ready

    def requestFetching(self, key):  # noqa: ANN001, ANN002
        self.requested.append(key)
        if self.pluginToServe:
            self.known.add(self.pluginToServe)  # like xmlDownloaded


class FakeInstallerDataModule:
    def __init__(self, known: set, repositories) -> None:  # noqa: ANN001
        self._known = known
        self.repositories = repositories
        self.plugins = types.SimpleNamespace(
            all=lambda: {key: {} for key in self._known}
        )


def test_installer_key_derives_from_file_name():
    gateway = makeGateway()
    key = gateway._installerKey(
        FakeEntity("TopoProfile Studio", "topoprofilestudio.1.0.0.zip")
    )
    assert key == "topoprofilestudio"
    assert gateway._installerKey(FakeEntity("QuickWKT", "QuickWKT.3.4.zip")) == "QuickWKT"
    assert gateway._installerKey(FakeEntity("OnlyName")) == "OnlyName"


def test_ensure_installer_data_skips_fetch_when_known():
    data = FakeInstallerDataModule({"SomePlugin"}, FakeRepositories(False, set()))
    package = installStubModule("pyplugin_installer", installer_data=data)
    package.instance = lambda: None
    gateway = makeGateway()
    gateway._ensureInstallerData("SomePlugin")
    assert data.repositories.requested == []
    teardownStubModules()


def test_ensure_installer_data_fetches_when_unknown():
    known: set = set()
    data = FakeInstallerDataModule(
        known, FakeRepositories(True, known, pluginToServe="SomePlugin")
    )
    package = installStubModule("pyplugin_installer", installer_data=data)
    package.instance = lambda: None
    gateway = makeGateway()
    gateway._ensureInstallerData("SomePlugin", timeout=1.0)
    assert sorted(data.repositories.requested) == ["official", "third-party"]
    teardownStubModules()


def test_ensure_installer_data_fails_clearly_when_absent():
    data = FakeInstallerDataModule(set(), FakeRepositories(True, set()))
    package = installStubModule("pyplugin_installer", installer_data=data)
    package.instance = lambda: None
    gateway = makeGateway()
    try:
        gateway._ensureInstallerData("Unknown", timeout=0.2)
        raised = False
    except RuntimeError as error:
        raised = True
        assert "not in the fetched plugin lists" in str(error)
    assert raised
    teardownStubModules()


def test_qgis4_instance_entry_point_is_used():
    recorder = Recording()
    package = installStubModule(
        "pyplugin_installer",
        installer_data=FakeInstallerDataModule({"SomePlugin"}, FakeRepositories(True, set())),
    )
    package.instance = lambda: recorder
    gateway = makeGateway()
    gateway.install(FakeEntity("SomePlugin"))
    gateway.uninstall(FakeEntity("SomePlugin"))
    assert recorder.calls == [
        ("installPlugin", "SomePlugin"),
        ("uninstallPlugin", "SomePlugin"),
    ]
    teardownStubModules()


def test_qgis3_singleton_is_the_fallback():
    recorder = Recording()
    package = installStubModule("pyplugin_installer")

    def gone():
        raise RuntimeError("instance unavailable")

    package.instance = gone
    installerModule = installStubModule("pyplugin_installer.installer")
    installerModule.installer = recorder
    gateway = makeGateway()
    gateway.install(FakeEntity("SomePlugin"))
    assert recorder.calls == [("installPlugin", "SomePlugin")]
    teardownStubModules()


def test_reinstall_maps_to_install_on_qgis4():
    recorder = Recording()  # no reinstallPlugin attribute: QGIS 4 shape
    package = installStubModule("pyplugin_installer")
    package.instance = lambda: recorder
    gateway = makeGateway()
    gateway.reinstall(FakeEntity("SomePlugin"))
    assert recorder.calls == [("installPlugin", "SomePlugin")]
    teardownStubModules()


def test_reinstall_uses_dedicated_entry_point_when_available():
    recorder = Recording()
    recorder.reinstallPlugin = lambda key, quiet=False: recorder.calls.append(
        ("reinstallPlugin", key)
    )
    package = installStubModule("pyplugin_installer")
    package.instance = lambda: recorder
    gateway = makeGateway()
    gateway.reinstall(FakeEntity("SomePlugin"))
    assert recorder.calls == [("reinstallPlugin", "SomePlugin")]
    teardownStubModules()


def test_unresolvable_installer_opens_the_manager():
    for name in ("pyplugin_installer", "pyplugin_installer.installer"):
        sys.modules[name] = types.ModuleType(name)  # imports succeed, API absent
    sys.modules["pyplugin_installer"].instance = lambda: None
    iface = FakeIface()
    gateway = makeGateway(iface)
    gateway.install(FakeEntity("SomePlugin"))
    assert iface.shown, "the plugin manager opens as the fallback"
    assert any("plugin manager" in m for m in gateway.reporter.infos)
    teardownStubModules()
