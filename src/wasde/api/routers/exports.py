# src/wasde/api/routers/exports.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wasde.api.db import get_db
from wasde.api.download import stream_download
from wasde.config import settings
from wasde.models.exports import ExportPaceResponse

router = APIRouter()


@router.get("/pace", response_model=list[ExportPaceResponse])
def get_export_pace(commodity: str | None = None) -> list[ExportPaceResponse]:
    """Current marketing year export pace vs. USDA annual target."""
    try:
        with get_db() as db:
            where = "WHERE commodity = ?" if commodity else ""
            params: list[object] = [commodity] if commodity else []
            rows = db.execute(
                f"SELECT commodity, marketing_year, cumulative_exports_mt, usda_target_mt, pace_pct, as_of_date FROM gold_export_pace {where} ORDER BY pace_pct DESC NULLS LAST",
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
def get_export_destinations(commodity: str = "Soybeans", top_n: int = 10) -> list[dict]:
    """Top export destinations for a commodity by cumulative volume."""
    try:
        with get_db() as db:
            silver_exports = str(settings.silver_dir / "exports.parquet")
            rows = db.execute(
                f"SELECT destination, SUM(net_sales_mt) AS total_mt FROM read_parquet('{silver_exports}') WHERE commodity = ? GROUP BY destination ORDER BY total_mt DESC LIMIT ?",
                [commodity, top_n],
            ).fetchall()
            return [{"destination": r[0], "total_mt": r[1]} for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/pace/download")
def download_export_pace(commodity: str | None = None, format: str = "csv"):
    """Download export pace data as CSV or XLSX."""
    try:
        with get_db() as db:
            where = "WHERE commodity = ?" if commodity else ""
            params: list[object] = [commodity] if commodity else []
            rows = db.execute(
                f"SELECT commodity, marketing_year, cumulative_exports_mt, usda_target_mt, pace_pct, as_of_date FROM gold_export_pace {where} ORDER BY pace_pct DESC NULLS LAST",
                params,
            ).fetchall()
            cols = [d[0] for d in db.description]
            data = [dict(zip(cols, row)) for row in rows]
            return stream_download(
                data, filename=f"export_pace_{commodity or 'all'}", fmt=format
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
