# src/wasde/models/psd.py
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class PSDRecord(BaseModel):
    report_date: date
    commodity: str
    country: str
    marketing_year: int
    attribute: str
    value: float | None
    unit: str

    @field_validator("commodity", "country", "attribute", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> str:
        return str(v).strip()


class SupplyDemandResponse(BaseModel):
    report_date: date
    commodity: str
    country: str
    marketing_year: int
    production: float | None
    beginning_stocks: float | None
    imports: float | None
    domestic_total: float | None
    exports: float | None
    ending_stocks: float | None
    stock_to_use_pct: float | None
    unit: str
