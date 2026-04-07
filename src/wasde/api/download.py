# src/wasde/api/download.py
"""Shared download helper — converts DuckDB result to CSV or XLSX stream."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pandas as pd
from fastapi.responses import StreamingResponse

if TYPE_CHECKING:
    import duckdb


def stream_download(
    result: duckdb.DuckDBPyRelation | list[dict],
    *,
    filename: str,
    fmt: str = "csv",
    columns: list[str] | None = None,
) -> StreamingResponse:
    """Convert a DuckDB result or list of dicts to a downloadable response.

    Args:
        result: DuckDB query result (with .fetchdf()) or list of dicts.
        filename: Base filename without extension.
        fmt: Output format — "csv" or "xlsx".
        columns: Optional column names (used when result is a raw fetchall).

    Returns:
        StreamingResponse with appropriate content-type and disposition.
    """
    if isinstance(result, list):
        df = pd.DataFrame(result)
    elif hasattr(result, "fetchdf"):
        df = result.fetchdf()
    else:
        df = pd.DataFrame(result)

    if fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    # Default: CSV
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
