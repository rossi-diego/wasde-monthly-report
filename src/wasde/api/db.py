# src/wasde/api/db.py
"""DuckDB connection factory — one connection per request to avoid concurrency bugs."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import duckdb

from wasde.config import settings


@contextmanager
def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Open a fresh read-only DuckDB connection and close it when done."""
    db_path = settings.duckdb_path
    if db_path.exists():
        con = duckdb.connect(str(db_path), read_only=True)
    else:
        con = duckdb.connect(":memory:")
    try:
        yield con
    finally:
        con.close()
