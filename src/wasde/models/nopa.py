# src/wasde/models/nopa.py
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class NOPARecord(BaseModel):
    report_date: date
    crush_million_bu: float
    oil_stocks_million_lbs: float

    @field_validator("crush_million_bu", "oil_stocks_million_lbs", mode="before")
    @classmethod
    def parse_numeric(cls, v: object) -> float:
        if isinstance(v, str):
            return float(v.replace(",", "").strip())
        return float(str(v))


class NOPACrushResponse(BaseModel):
    report_date: date
    crush_million_bu: float
    oil_stocks_million_lbs: float
    crush_margin_usd_per_bu: float | None
