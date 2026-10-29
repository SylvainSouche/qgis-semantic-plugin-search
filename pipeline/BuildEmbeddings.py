"""Build the per QGIS version embeddings database.

Reads the catalogue, the readme files and the static model, embeds each
plugin with the exact same tokenizer and mean pooling the plugin uses for
queries, and writes the distributable SQLite database.

Usage:
    python pipeline/BuildEmbeddings.py \
        --catalogue build/plugins-4.2.xml \
        --readmes build/plugins-4.2 \
        --model model/EmbeddingModel.npz \
        --universe 4 \
        --output build/Embeddings-4.sqlite
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.PluginCatalogue import PluginRecord, parseCatalogue, safePluginFileName  # noqa: E402
from pipeline.TextPreparation import preparePluginText  # noqa: E402
from SemanticPluginSearch.Data.StaticModelLoader import FORMAT_ID  # noqa: E402
from SemanticPluginSearch.Domain.WordPieceTokenizer import WordPieceTokenizer  # noqa: E402
from SemanticPluginSearch.Data.StaticModelLoader import NpzStaticModel  # noqa: E402

SCHEMA_VERSION = 1


class EmbeddingDatabaseWriter:
    """Writes the distributable SQLite embeddings database."""

    def __init__(self, model: NpzStaticModel, tokenizer: WordPieceTokenizer) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.readmeUrls: dict[int, str] = {}

    def build(
        self,
        records: list[PluginRecord],
        readmeDir: Path,
        universe: str,
        outputPath: Path,
        buildStamp: str,
        catalogueSource: str,
        readmeUrls: dict[int, str] | None = None,
    ) -> int:
        """Write the database and return the number of plugins embedded."""
        outputPath.parent.mkdir(parents=True, exist_ok=True)
        # Regenerate from scratch: a stale file would collide with CREATE TABLE.
        outputPath.unlink(missing_ok=True)
        self.readmeUrls = readmeUrls or {}
        vectors: list[tuple[int, bytes]] = []
        rows: list[tuple] = []
        for record in sorted(records, key=lambda item: (item.name.casefold(), item.pluginId)):
            embedding = self.embedRecord(record, readmeDir)
            rows.append(self._pluginRow(record))
            vectors.append((record.pluginId, embedding.astype(np.float32).tobytes()))
        connection = sqlite3.connect(outputPath)
        try:
            self._writeSchema(connection, rows, vectors, universe, buildStamp, catalogueSource)
        finally:
            connection.close()
        return len(rows)

    def embedRecord(self, record: PluginRecord, readmeDir: Path) -> np.ndarray:
        text = preparePluginText(record, self._readmeOf(record, readmeDir))
        tokenIds = self.tokenizer.encode(text)
        if not tokenIds:
            return np.zeros(self.model.dimension(), dtype=np.float32)
        matrix = self.model.vectors()
        mean = matrix[tokenIds].mean(axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            return np.zeros(self.model.dimension(), dtype=np.float32)
        return mean / norm

    @staticmethod
    def _readmeOf(record: PluginRecord, readmeDir: Path) -> str | None:
        candidate = readmeDir / (safePluginFileName(record.name) + ".md")
        if not candidate.is_file():
            return None
        try:
            return candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def _pluginRow(self, record: PluginRecord) -> tuple:
        return (
            record.pluginId,
            record.name,
            record.version,
            record.authorName,
            record.description,
            record.about,
            record.tagsText(),
            record.repository,
            record.homepage,
            record.tracker,
            record.downloadUrl,
            record.iconUrl,  # icon_url
            record.downloads,
            record.averageVote,
            record.ratingVotes,
            int(record.experimental),
            int(record.deprecated),
            int(record.server),
            record.qgisMinimum,
            record.qgisMaximum,
            self.readmeUrls.get(record.pluginId, ""),  # readme_url
            record.updateDate,
    )

    def _writeSchema(
        self,
        connection: sqlite3.Connection,
        rows: list[tuple],
        vectors: list[tuple[int, bytes]],
        universe: str,
        buildStamp: str,
        catalogueSource: str,
    ) -> None:
        connection.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE plugins (
                plugin_id INTEGER PRIMARY KEY,
                name TEXT, version TEXT, author TEXT,
                description TEXT, about TEXT, tags TEXT,
                repository TEXT, homepage TEXT, tracker TEXT,
                download_url TEXT, icon_url TEXT,
                downloads INTEGER, average_vote REAL, votes INTEGER,
                experimental INTEGER, deprecated INTEGER, server INTEGER,
                qgis_minimum TEXT, qgis_maximum TEXT,
                readme_url TEXT, update_date TEXT
            );
            CREATE TABLE vectors (
                plugin_id INTEGER PRIMARY KEY,
                embedding BLOB
            );
            """
        )
        connection.executemany(
            "INSERT INTO plugins VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        connection.executemany(
            "INSERT INTO vectors VALUES (?,?)",
            vectors,
        )
        connection.executemany(
            "INSERT INTO meta VALUES (?,?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("universe", universe),
                ("model_id", self.model.modelId()),
                ("model_dim", str(self.model.dimension())),
                ("build_stamp", buildStamp),
                ("plugin_count", str(len(rows))),
                ("generator", f"qgis-semantic-plugin-search/{FORMAT_ID}"),
                ("catalogue_source", catalogueSource),
            ],
        )
        connection.commit()


def defaultBuildStamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", required=True, help="plugins-<version>.xml path")
    parser.add_argument("--readmes", required=True, help="Directory of readme .md files")
    parser.add_argument("--model", required=True, help="Static model .npz path")
    parser.add_argument("--universe", required=True, help='"3" or "4"')
    parser.add_argument("--output", required=True, help="Output .sqlite path")
    parser.add_argument(
        "--readme-urls",
        default=None,
        help="Optional JSON mapping pluginId to resolved readme URL",
    )
    parser.add_argument("--build-stamp", default=None)
    parser.add_argument(
        "--catalogue-source", default="", help="Catalogue URL for provenance"
    )
    args = parser.parse_args(argv)

    model = NpzStaticModel.load(Path(args.model))
    tokenizer = WordPieceTokenizer(model.vocabulary())
    records = parseCatalogue(Path(args.catalogue).read_bytes())
    readmeUrls: dict[int, str] = {}
    if args.readme_urls and Path(args.readme_urls).is_file():
        readmeUrls = {
            int(pluginId): url
            for pluginId, url in json.loads(
                Path(args.readme_urls).read_text(encoding="utf-8")
            ).items()
        }
    writer = EmbeddingDatabaseWriter(model, tokenizer)
    count = writer.build(
        records=records,
        readmeDir=Path(args.readmes),
        universe=args.universe,
        outputPath=Path(args.output),
        buildStamp=args.build_stamp or defaultBuildStamp(),
        catalogueSource=args.catalogue_source,
        readmeUrls=readmeUrls,
    )
    print(f"Wrote {args.output}: {count} plugins, dim {model.dimension()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 0f87-6ae3-6986-9d64
# @impl 0f87-6ae3-6986-d290
