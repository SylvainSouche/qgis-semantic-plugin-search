"""Write an int8 copy of an embeddings database.

The copy is identical except for the vectors table, stored as int8 with a
per vector scale (SemanticPluginSearch/Data/VectorCodec.py), and the meta
key vector_format. Plugin versions that read only float32 keep using the
original file: the index lists the copies separately (universes_q8).

    python pipeline/QuantizeDatabase.py build/Embeddings-3.sqlite build/Embeddings-3-q8.sqlite
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from SemanticPluginSearch.Data.VectorCodec import (  # noqa: E402
    FLOAT32,
    INT8_SCALED,
    VECTOR_FORMAT_KEY,
    decodeVector,
    encodeInt8,
)


def quantizeDatabase(source: Path, target: Path) -> Path:
    """Copy source to target with int8 vectors; return target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    shutil.copyfile(source, temporary)
    connection = sqlite3.connect(temporary)
    try:
        meta = dict(connection.execute("SELECT key, value FROM meta"))
        if meta.get(VECTOR_FORMAT_KEY, FLOAT32) != FLOAT32:
            raise ValueError(f"{source} is not a float32 database")
        dim = int(meta["model_dim"])
        rows = connection.execute("SELECT plugin_id, embedding FROM vectors").fetchall()
        connection.executemany(
            "UPDATE vectors SET embedding = ? WHERE plugin_id = ?",
            [(encodeInt8(decodeVector(blob, dim)), pid) for pid, blob in rows])
        connection.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                           (VECTOR_FORMAT_KEY, INT8_SCALED))
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()
    temporary.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    target = quantizeDatabase(Path(args[0]), Path(args[1]))
    print(f"Wrote {target}: {Path(args[0]).stat().st_size / 1e6:.1f} MB ->"
          f" {target.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    np.seterr(all="raise")
    sys.exit(main())
