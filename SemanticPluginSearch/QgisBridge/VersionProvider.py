"""QGIS version reporting for asset universe selection."""
from __future__ import annotations

from qgis.core import Qgis

from ..Domain.Ports import VersionProvider


class QgisVersionProvider(VersionProvider):
    """Maps the running QGIS version onto the published asset universes."""

    def universe(self) -> str:
        return str(Qgis.QGIS_VERSION_INT // 10000)

    def qgisVersion(self) -> str:
        return Qgis.QGIS_VERSION
