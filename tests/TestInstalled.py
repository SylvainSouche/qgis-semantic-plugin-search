"""Installed state: the disk snapshot, the action states and the badges.

Regression covered: on QGIS 4.2.3 no installed plugin was ever recognised,
so Upgrade, Reinstall and Uninstall never enabled. The gateway looked the
display name up in qgis.utils.plugins, which is keyed by folder name and
holds plugin instances without a version.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

from SemanticPluginSearch.Controllers.ActionController import ActionController
from SemanticPluginSearch.Data.InstalledPlugins import scanInstalledPlugins
from SemanticPluginSearch.Domain.Entities import InstalledPlugin, PluginInfo, SearchResult
from SemanticPluginSearch.Domain.Installed import (
    actionStatesFor,
    findInstalled,
    installedBadges,
    versionIsNewer,
)
from tests.conftest import FakePluginManagerGateway, FakeReporter, FakeView


def info(pluginId: int, name: str, version: str = "1.0.0", fileName: str = "") -> PluginInfo:
    return PluginInfo(pluginId=pluginId, name=name, version=version, fileName=fileName)


def writePlugin(root: Path, key: str, name: str, version: str) -> None:
    folder = root / key
    folder.mkdir(parents=True)
    (folder / "metadata.txt").write_text(
        f"[general]\nname={name}\nversion={version}\nabout=50% %done\n", encoding="utf-8"
    )


# ------------------------------------------------------------- disk scan


def test_scan_reads_key_name_and_version_from_metadata(tmp_path: Path):
    writePlugin(tmp_path / "user", "topoprofilestudio", "TopoProfile Studio", "1.0.0")
    (tmp_path / "user" / "not_a_plugin").mkdir()
    installed = scanInstalledPlugins([tmp_path / "user", tmp_path / "missing"])
    assert installed == {
        "topoprofilestudio": InstalledPlugin("topoprofilestudio", "TopoProfile Studio", "1.0.0")
    }


def test_scan_first_path_wins_like_qgis(tmp_path: Path):
    writePlugin(tmp_path / "user", "processing", "Processing", "9.9")
    writePlugin(tmp_path / "system", "processing", "Processing", "2.12.99")
    installed = scanInstalledPlugins([tmp_path / "user", tmp_path / "system"])
    assert installed["processing"].version == "9.9"


def test_scan_skips_unreadable_metadata(tmp_path: Path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "metadata.txt").write_bytes(b"\xff\xfe not ini")
    assert scanInstalledPlugins([tmp_path]) == {}


# ------------------------------------------------------------ matching


def test_match_by_installer_key_from_file_name():
    installed = {"topoprofilestudio": InstalledPlugin("topoprofilestudio", "Other", "1.0")}
    target = info(1, "TopoProfile Studio", fileName="topoprofilestudio.1.0.0.zip")
    found = findInstalled(target, installed)
    assert found is installed["topoprofilestudio"]


def test_match_case_insensitively_then_by_declared_name():
    installed = {
        "quickwkt": InstalledPlugin("quickwkt", "QuickWKT", "3.1"),
        "odd_folder": InstalledPlugin("odd_folder", "Odd Plugin", "0.1"),
    }
    quick = info(1, "QuickWKT", fileName="QuickWKT.3.4.zip")
    odd = info(2, "Odd Plugin", fileName="oddplugin.0.2.zip")
    assert findInstalled(quick, installed).key == "quickwkt"
    assert findInstalled(odd, installed).key == "odd_folder"
    assert findInstalled(info(3, "Absent", fileName="absent.1.zip"), installed) is None


def test_version_comparison_ignores_trailing_zeros():
    assert versionIsNewer("2.0", "1.9.9")
    assert not versionIsNewer("1.0", "1.0.0")
    assert not versionIsNewer("1.0.0", "1.0")
    assert versionIsNewer("1.10", "1.9")


# ------------------------------------------------------- states, badges


def test_absent_plugin_offers_install_only():
    states = actionStatesFor(info(1, "X", fileName="x.1.zip"), {})
    assert states.canInstall
    assert not (states.canUpgrade or states.canReinstall or states.canUninstall)


def test_installed_plugin_offers_reinstall_uninstall_and_upgrade_when_newer():
    installed = {"x": InstalledPlugin("x", "X", "1.0")}
    older = actionStatesFor(info(1, "X", "2.0", "x.2.0.zip"), installed)
    assert not older.canInstall and older.canUpgrade and older.canReinstall and older.canUninstall
    assert older.installedVersion == "1.0"
    same = actionStatesFor(info(1, "X", "1.0", "x.1.0.zip"), installed)
    assert not same.canUpgrade and same.canReinstall and same.canUninstall


def test_badges_mark_installed_and_upgradeable_rows():
    installed = {"a": InstalledPlugin("a", "A", "1.0"), "b": InstalledPlugin("b", "B", "1.0")}
    badges = installedBadges(
        [info(1, "A", "1.0", "a.1.0.zip"), info(2, "B", "1.5", "b.1.5.zip"), info(3, "C")],
        installed,
    )
    assert badges == {1: "installed", 2: "upgradeable"}


# ---------------------------------------------------------- controller


def test_controller_states_follow_the_disk_snapshot():
    view = FakeView()
    gateway = FakePluginManagerGateway({"x": InstalledPlugin("x", "X", "1.0")})
    controller = ActionController(gateway, FakeReporter())
    controller.refreshStates(view, info(1, "X", "2.0", "x.2.0.zip"))
    assert view.actionStates[-1].canUpgrade and not view.actionStates[-1].canInstall


def test_unreadable_state_disables_everything_rather_than_offering_install():
    class BrokenGateway(FakePluginManagerGateway):
        def installedPlugins(self):  # noqa: ANN201
            raise OSError("permission denied")

    view = FakeView()
    reporter = FakeReporter()
    controller = ActionController(BrokenGateway(), reporter)
    controller.refreshStates(view, info(1, "X", fileName="x.1.zip"))
    states = view.actionStates[-1]
    assert not (states.canInstall or states.canUpgrade)
    assert not (states.canReinstall or states.canUninstall)
    assert reporter.warnings


def test_states_and_badges_refresh_after_an_action():
    class InstallingGateway(FakePluginManagerGateway):
        def install(self, plugin) -> None:  # noqa: ANN001
            super().install(plugin)
            self.installed["x"] = InstalledPlugin("x", "X", plugin.version)

    view = FakeView()
    gateway = InstallingGateway()
    controller = ActionController(gateway, FakeReporter())
    target = info(1, "X", "1.0", "x.1.0.zip")
    controller.refreshInstalled(view, [SearchResult(info=target, score=0.9)])
    assert view.badges[-1] == {}
    controller.runAction(view, "install", target)
    assert view.badges[-1] == {1: "installed"}
    assert view.actionStates[-1].canUninstall and not view.actionStates[-1].canInstall


# ------------------------------------------------------------- gateway


def test_gateway_scans_the_plugin_paths_qgis_uses(tmp_path: Path):
    from tests.TestInstallerGateway import makeGateway

    writePlugin(tmp_path, "processing", "Processing", "2.12.99")
    utils = types.ModuleType("qgis.utils")
    utils.plugin_paths = [str(tmp_path)]
    previous = sys.modules.get("qgis.utils")
    sys.modules["qgis.utils"] = utils
    qgis = sys.modules["qgis"]
    previousAttribute = getattr(qgis, "utils", None)
    qgis.utils = utils
    try:
        installed = makeGateway().installedPlugins()
    finally:
        if previous is None:
            sys.modules.pop("qgis.utils", None)
        else:
            sys.modules["qgis.utils"] = previous
        if previousAttribute is None:
            del qgis.utils
        else:
            qgis.utils = previousAttribute
    assert installed["processing"].version == "2.12.99"
