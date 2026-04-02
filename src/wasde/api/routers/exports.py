# src/wasde/api/routers/exports.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from wasde.config import settings
from wasde.models.exports import ExportPaceResponse

router = APIRouter()


def _db(request: Request):  # type: ignore[return]
    return request.app.state.db


@router.get("/pace", response_model=list[ExportPaceResponse])
def get_export_pace(
    request: Request,
    commodity: str | None = None,
) -> list[ExportPaceResponse]:
    """Current marketing year export pace vs. USDA annual target."""
    db = _db(request)
    try:
        where = "WHERE commodity = ?" if commodity else ""
        params: list[object] = [commodity] if commodity else []
        rows = db.execute(
            f"""
            SELECT commodity, marketing_year, cumulative_exports_mt,
                   usda_target_mt, pace_pct, as_of_date
            FROM gold_export_pace
            {where}
            ORDER BY pace_pct DESC NULLS LAST
            """,
            params,
        ).fetchall()
        return [
            ExportPaceResponse(
                commodity=r[0],
                marketing_year=r[1],
                cumulative_exports_mt=r[2],
                usda_target_mt=r[3],
                pace_pct=r[4],
                as_of_date=r[5],
            )
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/destinations", response_model=list[dict])
def get_export_destinations(
    request: Request,
    commodity: str = "Soybeans",
    top_n: int = 10,
) -> list[dict]:
    """Top export destinations for a commodity by cumulative volume."""
    db = _db(request)
    try:
        silver_exports = str(settings.silver_dir / "exports.parquet")
        rows = db.execute(
            f"""
            SELECT destination, SUM(net_sales_mt) AS total_mt
            FROM read_parquet('{silver_exports}')
            WHERE commodity = ?
            GROUP BY destination
            ORDER BY total_mt DESC
            LIMIT ?
            """,
            [commodity, top_n],
        ).fetchall()
        return [{"destination": r[0], "total_mt": r[1]} for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
