"""QGIS version reporting for asset universe selection."""
from __future__ import annotations

from qgis.core import Qgis

from ..Domain.Ports import VersionProvider


class QgisVersionProvider(VersionProvider):
    """Maps the running QGIS version onto the published asset universes.

    The version accessors have moved between QGIS 3 and 4, so every access
    falls back through the known spellings.
    """

    def universe(self) -> str:
        major = _versionText().split(".")[0]
        return major if major.isdigit() else "3"

    def qgisVersion(self) -> str:
        return _versionText()


def _versionText() -> str:
    try:
        return str(Qgis.QGIS_VERSION)
    except AttributeError:
        pass
    try:
        return str(Qgis.version())
    except AttributeError:
        pass
    try:
        # QGIS_VERSION_INT 40203 encodes 4.2.3.
        encoded = int(Qgis.QGIS_VERSION_INT)
        return f"{encoded // 10000}.{encoded // 100 % 100}.{encoded % 100}"
    except AttributeError:
        return "0.0.0"
