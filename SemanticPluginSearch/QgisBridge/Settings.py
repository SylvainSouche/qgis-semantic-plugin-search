"""Settings defaults and QSettings access.

The published index location is the only configuration the plugin needs;
it defaults to the project GitHub releases and can be overridden with the
QSettings key below (e.g. for a mirror or a staging repository). Window
state (visibility toggles, geometry, splitter) is persisted under the ui
prefix.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import QSettings

ORGANIZATION = "SemanticPluginSearch"
APPLICATION = "SemanticPluginSearch"
INDEX_URL_KEY = "embeddings/indexUrl"
UI_PREFIX = f"{ORGANIZATION}/ui"
UI_INCLUDE_EXPERIMENTAL = f"{UI_PREFIX}/includeExperimental"
UI_INCLUDE_DEPRECATED = f"{UI_PREFIX}/includeDeprecated"
UI_GEOMETRY = f"{UI_PREFIX}/geometry"
UI_SPLITTER = f"{UI_PREFIX}/splitter"
# Placeholder repository: replace once the project GitHub repository is
# chosen; see README.md.
DEFAULT_REPOSITORY = "SylvainSouche/qgis-semantic-plugin-search"


def defaultIndexUrl() -> str:
    return (
        f"https://github.com/{DEFAULT_REPOSITORY}/releases/latest/download/index.json"
    )


def configuredIndexUrl() -> str:
    settings = QSettings()
    return str(
        settings.value(
            f"{ORGANIZATION}/{INDEX_URL_KEY}",
            defaultIndexUrl(),
            type=str,
        )
    )
