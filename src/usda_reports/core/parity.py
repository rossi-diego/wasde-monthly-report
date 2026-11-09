"""Content fingerprint of a Parquet file, independent of row order and file encoding.

Two files with the same fingerprint hold the same rows (as multisets) with the same column
names and types, even if writer versions, row groups or compression differ. Used by the
parity gate between a rebuilt dataset and a published release asset.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class Fingerprint:
    rows: int
    schema: tuple[tuple[str, str], ...]
    content_sha256: str


def fingerprint(path: Path) -> Fingerprint:
    """Row count, schema and sha256 over the sorted per-row hashes of a Parquet file."""
    p = path.as_posix()
    con = duckdb.connect()
    try:
        schema = tuple(
            (str(name), str(typ))
            for name, typ, *_ in con.execute(
                f"describe select * from read_parquet('{p}')"
            ).fetchall()
        )
        # Each row is serialised by DuckDB's struct-to-text cast (columns named, nulls explicit),
        # hashed, and the sorted hashes are folded into one digest.
        hashes = con.execute(
            f"select md5(cast(t as varchar)) as h from read_parquet('{p}') as t order by h"
        ).fetchall()
    finally:
        con.close()
    digest = hashlib.sha256()
    for (h,) in hashes:
        digest.update(h.encode("ascii"))
        digest.update(b"\n")
    return Fingerprint(rows=len(hashes), schema=schema, content_sha256=digest.hexdigest())
