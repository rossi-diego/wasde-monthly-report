# src/wasde/api/routers/supply_demand.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from wasde.models.psd import SupplyDemandResponse

router = APIRouter()


def _db(request: Request):  # type: ignore[return]
    return request.app.state.db


@router.get("/", response_model=list[SupplyDemandResponse])
def get_supply_demand(
    request: Request,
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
    db = _db(request)
    try:
        where = "WHERE commodity = ? AND country = ?"
        params: list[object] = [commodity, country]
        if marketing_year is not None:
            where += " AND marketing_year = ?"
            params.append(marketing_year)

        rows = db.execute(
            f"""
            SELECT * FROM gold_supply_demand
            {where}
            ORDER BY report_date DESC, marketing_year DESC
            LIMIT 500
            """,
            params,
        ).fetchall()
        cols = [d[0] for d in db.description]
        return [SupplyDemandResponse(**dict(zip(cols, row))) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stock-to-use", response_model=list[dict])
def get_stock_to_use(
    request: Request,
    commodity: str = "Soybeans",
    country: str = "World",
) -> list[dict]:
    """Historical stock-to-use ratio time series."""
    db = _db(request)
    try:
        rows = db.execute(
            """
            SELECT report_date, marketing_year, stock_to_use_pct
            FROM gold_supply_demand
            WHERE commodity = ? AND country = ? AND stock_to_use_pct IS NOT NULL
            ORDER BY report_date, marketing_year
            """,
            [commodity, country],
        ).fetchall()
        return [
            {"report_date": str(r[0]), "marketing_year": r[1], "stock_to_use_pct": r[2]}
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/revisions", response_model=list[dict])
def get_revisions(
    request: Request,
    commodity: str = "Soybeans",
    marketing_year: int = 2024,
    country: str = "World",
) -> list[dict]:
    """How ending-stocks estimates changed across monthly WASDE releases."""
    db = _db(request)
    try:
        rows = db.execute(
            """
            SELECT report_date, ending_stocks, revision_ending_stocks
            FROM gold_supply_demand
            WHERE commodity = ? AND marketing_year = ? AND country = ?
              AND ending_stocks IS NOT NULL
            ORDER BY report_date
            """,
            [commodity, marketing_year, country],
        ).fetchall()
        return [
            {
                "report_date": str(r[0]),
                "ending_stocks": r[1],
                "revision": r[2],
            }
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
