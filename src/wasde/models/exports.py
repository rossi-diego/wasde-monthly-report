# src/wasde/models/exports.py
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class ExportRecord(BaseModel):
    week_ending: date
    commodity: str
    destination: str
    net_sales_mt: float
    cumulative_exports_mt: float

    @field_validator("commodity", "destination", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> str:
        return str(v).strip()


class ExportPaceResponse(BaseModel):
    commodity: str
    marketing_year: int
    cumulative_exports_mt: float
    usda_target_mt: float | None
    pace_pct: float | None
    as_of_date: date
