"""SQLite backed read side of the distributed embeddings database.

Database layout (written by the pipeline, see pipeline/BuildEmbeddings.py):

    meta(key TEXT PRIMARY KEY, value TEXT)
        schema_version, universe, model_id, model_dim, build_stamp,
        plugin_count, generator, catalogue_source
    plugins(plugin_id INTEGER PRIMARY KEY, name TEXT, version TEXT, ...)
    vectors(plugin_id INTEGER PRIMARY KEY, embedding BLOB)

Plugin rows are L2 normalized float32 blobs aligned with the plugin id list,
so a cosine similarity is a single matrix product.

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from ..Domain.Entities import PluginInfo
from ..Domain.Ports import PluginVectorStore

SCHEMA_VERSION = 2

_PLUGIN_COLUMNS = (
    "plugin_id, name, version, author, description, about, tags, repository,"
    " homepage, tracker, download_url, file_name, icon_url, downloads, average_vote,"
    " votes, experimental, deprecated, server, qgis_minimum, qgis_maximum,"
    " readme_url, update_date"
)


class DatabaseMissingError(FileNotFoundError):
    """The local embeddings database has not been downloaded yet."""


class SqliteVectorStore(PluginVectorStore):
    """Opens a distributed database read only and serves it to the search."""

    def __init__(
        self,
        meta: dict[str, str],
        infos: dict[int, PluginInfo],
        pluginIds: list[int],
        matrix: np.ndarray,
    ) -> None:
        self._meta = meta
        self._infos = infos
        self._pluginIds = pluginIds
        self._matrix = matrix

    @staticmethod
    def open(path: Path) -> SqliteVectorStore:
        """Open the database at path or raise DatabaseMissingError."""
        if not path.is_file():
            raise DatabaseMissingError(str(path))
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            meta = {
                key: value
                for key, value in connection.execute("SELECT key, value FROM meta")
            }
            if int(meta.get("schema_version", "-1")) != SCHEMA_VERSION:
                raise ValueError(
                    f"unsupported database schema version: {meta.get('schema_version')}"
                )
            infos: dict[int, PluginInfo] = {}
            pluginIds: list[int] = []
            # _PLUGIN_COLUMNS is a module constant, never user input.
            query = f"SELECT {_PLUGIN_COLUMNS} FROM plugins ORDER BY plugin_id"
            for row in connection.execute(query):
                info = _rowToInfo(row)
                infos[info.pluginId] = info
                pluginIds.append(info.pluginId)
            vectors: dict[int, bytes] = {}
            for pluginId, blob in connection.execute(
                "SELECT plugin_id, embedding FROM vectors"
            ):
                vectors[pluginId] = blob
        finally:
            connection.close()
        matrix = np.zeros((len(pluginIds), int(meta.get("model_dim", "0"))), dtype=np.float32)
        for position, pluginId in enumerate(pluginIds):
            blob = vectors.get(pluginId)
            if blob is not None:
                matrix[position] = np.frombuffer(blob, dtype=np.float32)
        return SqliteVectorStore(meta, infos, pluginIds, matrix)

    def buildStamp(self) -> str:
        return self._meta.get("build_stamp", "")

    def universe(self) -> str:
        return self._meta.get("universe", "")

    def modelId(self) -> str:
        return self._meta.get("model_id", "")

    def modelDim(self) -> int:
        return int(self._meta.get("model_dim", "0"))

    def pluginCount(self) -> int:
        return len(self._pluginIds)

    def pluginIds(self) -> list[int]:
        return list(self._pluginIds)

    def embeddings(self) -> np.ndarray:
        return self._matrix

    def pluginInfo(self, pluginId: int) -> PluginInfo | None:
        return self._infos.get(pluginId)

    def infos(self) -> dict[int, PluginInfo]:
        return dict(self._infos)

    def meta(self) -> dict[str, str]:
        return dict(self._meta)


def readDatabaseMeta(databasePath: Path, key: str) -> str:
    """Read one meta value without loading the whole store."""
    connection = sqlite3.connect(f"file:{databasePath}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError(f"meta key not found: {key}")
    return str(row[0])


def _rowToInfo(row: tuple) -> PluginInfo:
    (
        pluginId,
        name,
        version,
        author,
        description,
        about,
        tags,
        repository,
        homepage,
        tracker,
        downloadUrl,
        fileName,
        iconUrl,
        downloads,
        averageVote,
        votes,
        experimental,
        deprecated,
        server,
        qgisMinimum,
        qgisMaximum,
        readmeUrl,
        updateDate,
    ) = row
    return PluginInfo(
        pluginId=int(pluginId),
        name=name,
        version=version or "",
        author=author or "",
        description=description or "",
        about=about or "",
        tags=tuple(tag for tag in (tags or "").split(",") if tag),
        repository=repository or "",
        homepage=homepage or "",
        tracker=tracker or "",
        downloadUrl=downloadUrl or "",
        fileName=fileName or "",
        iconUrl=iconUrl or "",
        downloads=int(downloads or 0),
        averageVote=float(averageVote or 0.0),
        votes=int(votes or 0),
        experimental=bool(experimental),
        deprecated=bool(deprecated),
        server=bool(server),
        qgisMinimum=qgisMinimum or "",
        qgisMaximum=qgisMaximum or "",
        readmeUrl=readmeUrl or "",
        updateDate=updateDate or "",
    )
