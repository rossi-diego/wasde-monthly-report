# src/wasde/api/routers/wasde.py
"""WASDE CSV endpoints — revision tracking and latest S&D."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from wasde.api.db import get_db
from wasde.config import settings
from wasde.models.wasde import WASDELatestResponse, WASDERevisionResponse

router = APIRouter()


@router.get("/revisions", response_model=list[WASDERevisionResponse])
def get_wasde_revisions(
    commodity: Annotated[str, Query(description="e.g. Soybeans, Corn, Wheat")],
    marketing_year: Annotated[str | None, Query(description="e.g. 2024/25")] = None,
    region: Annotated[
        str | None, Query(description="e.g. World, United States")
    ] = None,
    attribute: Annotated[
        str | None, Query(description="e.g. Ending Stocks, Production")
    ] = None,
) -> list[WASDERevisionResponse]:
    """Month-by-month revision history for a commodity's S&D estimates."""
    try:
        with get_db() as db:
            where = "WHERE commodity = ?"
            params: list[object] = [commodity]
            if marketing_year is not None:
                where += " AND marketing_year = ?"
                params.append(marketing_year)
            if region is not None:
                where += " AND region = ?"
                params.append(region)
            if attribute is not None:
                where += " AND attribute = ?"
                params.append(attribute)
            rows = db.execute(
                f"SELECT * FROM gold_wasde_revisions {where} ORDER BY marketing_year, forecast_year, forecast_month LIMIT 2000",
                params,
            ).fetchall()
            cols = [d[0] for d in db.description]
            return [WASDERevisionResponse(**dict(zip(cols, row))) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/latest", response_model=list[WASDELatestResponse])
def get_wasde_latest(
    commodity: Annotated[str | None, Query(description="e.g. Soybeans")] = None,
    region: Annotated[str | None, Query(description="e.g. World")] = None,
    marketing_year: Annotated[str | None, Query(description="e.g. 2024/25")] = None,
) -> list[WASDELatestResponse]:
    """Latest pivoted S&D balance sheet from WASDE reports."""
    try:
        with get_db() as db:
            clauses: list[str] = []
            params: list[object] = []
            if commodity is not None:
                clauses.append("commodity = ?")
                params.append(commodity)
            if region is not None:
                clauses.append("region = ?")
                params.append(region)
            if marketing_year is not None:
                clauses.append("marketing_year = ?")
                params.append(marketing_year)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = db.execute(
                f"SELECT * FROM gold_wasde_latest {where} ORDER BY marketing_year DESC LIMIT 500",
                params,
            ).fetchall()
            cols = [d[0] for d in db.description]
            return [WASDELatestResponse(**dict(zip(cols, row))) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/commodities", response_model=list[str])
def get_wasde_commodities() -> list[str]:
    """Distinct commodity list available in WASDE data."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT DISTINCT commodity FROM gold_wasde_latest ORDER BY commodity"
            ).fetchall()
            return [r[0] for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reports", response_model=list[dict])
def get_wasde_reports() -> list[dict]:
    """List of available WASDE report months."""
    try:
        with get_db() as db:
            silver_wasde = str(settings.silver_dir / "wasde.parquet")
            rows = db.execute(f"""
                SELECT DISTINCT forecast_year, forecast_month, MIN(wasde_number) AS wasde_number, MIN(release_date) AS release_date
                FROM read_parquet('{silver_wasde}')
                GROUP BY forecast_year, forecast_month
                ORDER BY forecast_year DESC, forecast_month DESC
            """).fetchall()
            return [
                {
                    "forecast_year": r[0],
                    "forecast_month": r[1],
                    "wasde_number": r[2],
                    "release_date": str(r[3]),
                }
                for r in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
