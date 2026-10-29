"""Adapters exposing QGIS services through the Domain ports.

Every import of qgis lives in this package (the Presentation layer imports
Qt for widgets only). The adapters are deliberately thin; their behavior is
exercised inside QGIS, not by the automated suite.
"""
from __future__ import annotations

from .VersionProvider import QgisVersionProvider
from .PathsProvider import ProfilePathsProvider
from .Reporter import MessageBarReporter
from .QtJobRunner import QtJobRunner
from .PluginInstallerGateway import PluginInstallerGateway
from .Settings import configuredIndexUrl, defaultIndexUrl

__all__ = [
    "QgisVersionProvider",
    "ProfilePathsProvider",
    "MessageBarReporter",
    "QtJobRunner",
    "PluginInstallerGateway",
    "defaultIndexUrl",
    "configuredIndexUrl",
]
