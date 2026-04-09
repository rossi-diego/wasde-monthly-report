# src/wasde/api/routers/nopa.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wasde.api.db import get_db
from wasde.api.download import stream_download
from wasde.models.nopa import NOPACrushResponse

router = APIRouter()


@router.get("/crush", response_model=list[NOPACrushResponse])
def get_crush(months: int = 24) -> list[NOPACrushResponse]:
    """Monthly soybean crush volume and oil stocks."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT report_date, crush_million_bu, oil_stocks_million_lbs, crush_margin_usd_per_bu FROM gold_nopa_crush ORDER BY report_date DESC LIMIT ?",
                [months],
            ).fetchall()
            return [
                NOPACrushResponse(
                    report_date=r[0],
                    crush_million_bu=r[1],
                    oil_stocks_million_lbs=r[2],
                    crush_margin_usd_per_bu=r[3],
                )
                for r in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/rolling-crush", response_model=list[dict])
def get_rolling_crush(months: int = 36) -> list[dict]:
    """Monthly crush with 12-month rolling total."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT report_date, crush_million_bu, rolling_12m_crush FROM gold_nopa_crush ORDER BY report_date DESC LIMIT ?",
                [months],
            ).fetchall()
            return [
                {
                    "report_date": str(r[0]),
                    "crush_million_bu": r[1],
                    "rolling_12m_crush": r[2],
                }
                for r in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/crush/download")
def download_crush(months: int = 120, format: str = "csv"):
    """Download NOPA crush data as CSV or XLSX."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT report_date, crush_million_bu, oil_stocks_million_lbs, crush_margin_usd_per_bu, rolling_12m_crush FROM gold_nopa_crush ORDER BY report_date DESC LIMIT ?",
                [months],
            ).fetchall()
            cols = [d[0] for d in db.description]
            data = [dict(zip(cols, row)) for row in rows]
            return stream_download(data, filename="nopa_crush", fmt=format)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
