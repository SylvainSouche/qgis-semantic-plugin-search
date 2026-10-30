"""Settings defaults and QSettings access.

The published index location is the only configuration the plugin needs;
it defaults to the embeddings branch of the project repository and can be overridden with the
QSettings key below (e.g. for a mirror or a staging repository). Window
state (visibility toggles, geometry, splitter) is persisted under the ui
prefix.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import QSettings

ORGANIZATION = "SemanticPluginSearch"
APPLICATION = "SemanticPluginSearch"
INDEX_URL_KEY = "embeddings/indexUrl"
DATA_BRANCH = "embeddings"
UI_PREFIX = f"{ORGANIZATION}/ui"
UI_INCLUDE_EXPERIMENTAL = f"{UI_PREFIX}/includeExperimental"
UI_INCLUDE_DEPRECATED = f"{UI_PREFIX}/includeDeprecated"
UI_GEOMETRY = f"{UI_PREFIX}/geometry"
UI_SPLITTER = f"{UI_PREFIX}/splitter"
DEFAULT_REPOSITORY = "SylvainSouche/qgis-semantic-plugin-search"


def defaultIndexUrl() -> str:
    # The data branch the BuildEmbeddings workflow rewrites each run; the
    # files it names carry content hashes, so raw caching stays consistent.
    return (
        f"https://raw.githubusercontent.com/{DEFAULT_REPOSITORY}/{DATA_BRANCH}/index.json"
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
# @impl 4be9-6ae3-f849-7641
