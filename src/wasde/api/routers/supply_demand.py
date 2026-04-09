# src/wasde/api/routers/supply_demand.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from wasde.api.db import get_db
from wasde.api.download import stream_download
from wasde.models.psd import SupplyDemandResponse

router = APIRouter()


@router.get("/", response_model=list[SupplyDemandResponse])
def get_supply_demand(
    commodity: Annotated[
        str, Query(description="e.g. Soybeans, Corn, Wheat")
    ] = "Soybeans",
    country: Annotated[
        str, Query(description="e.g. World, United States, Brazil")
    ] = "World",
    marketing_year: Annotated[
        int | None, Query(description="Marketing year start, e.g. 2024")
    ] = None,
) -> list[SupplyDemandResponse]:
    """Latest supply & demand estimates per marketing year."""
    try:
        with get_db() as db:
            where = "WHERE commodity = ? AND country = ?"
            params: list[object] = [commodity, country]
            if marketing_year is not None:
                where += " AND marketing_year = ?"
                params.append(marketing_year)
            rows = db.execute(
                f"SELECT * FROM gold_supply_demand {where} ORDER BY report_date DESC, marketing_year DESC LIMIT 500",
                params,
            ).fetchall()
            cols = [d[0] for d in db.description]
            return [SupplyDemandResponse(**dict(zip(cols, row))) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stock-to-use", response_model=list[dict])
def get_stock_to_use(commodity: str = "Soybeans", country: str = "World") -> list[dict]:
    """Historical stock-to-use ratio time series."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT report_date, marketing_year, stock_to_use_pct FROM gold_supply_demand WHERE commodity = ? AND country = ? AND stock_to_use_pct IS NOT NULL ORDER BY report_date, marketing_year",
                [commodity, country],
            ).fetchall()
            return [
                {
                    "report_date": str(r[0]),
                    "marketing_year": r[1],
                    "stock_to_use_pct": r[2],
                }
                for r in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/revisions", response_model=list[dict])
def get_revisions(
    commodity: str = "Soybeans", marketing_year: int = 2024, country: str = "World"
) -> list[dict]:
    """How ending-stocks estimates changed across monthly WASDE releases."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT report_date, ending_stocks, revision_ending_stocks FROM gold_supply_demand WHERE commodity = ? AND marketing_year = ? AND country = ? AND ending_stocks IS NOT NULL ORDER BY report_date",
                [commodity, marketing_year, country],
            ).fetchall()
            return [
                {"report_date": str(r[0]), "ending_stocks": r[1], "revision": r[2]}
                for r in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/download")
def download_supply_demand(
    commodity: str = "Soybeans",
    country: str = "World",
    marketing_year: int | None = None,
    format: str = "csv",
):
    """Download supply & demand data as CSV or XLSX."""
    try:
        with get_db() as db:
            where = "WHERE commodity = ? AND country = ?"
            params: list[object] = [commodity, country]
            if marketing_year is not None:
                where += " AND marketing_year = ?"
                params.append(marketing_year)
            rows = db.execute(
                f"SELECT * FROM gold_supply_demand {where} ORDER BY report_date DESC, marketing_year DESC",
                params,
            ).fetchall()
            cols = [d[0] for d in db.description]
            data = [dict(zip(cols, row)) for row in rows]
            return stream_download(
                data,
                filename=f"supply_demand_{commodity}_{marketing_year or 'all'}",
                fmt=format,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/metadata")
def get_metadata() -> dict:
    """Available filter values — commodities, countries, marketing years."""
    try:
        with get_db() as db:
            commodities = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT commodity FROM gold_supply_demand ORDER BY commodity"
                ).fetchall()
            ]
            countries = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT country FROM gold_supply_demand ORDER BY country"
                ).fetchall()
            ]
            years = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT marketing_year FROM gold_supply_demand WHERE marketing_year IS NOT NULL ORDER BY marketing_year DESC"
                ).fetchall()
            ]
            return {
                "commodities": commodities,
                "countries": countries,
                "marketing_years": years,
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
