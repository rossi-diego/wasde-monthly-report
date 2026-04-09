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
    model_config = {"extra": "ignore"}

    report_date: date
    commodity: str
    country: str
    marketing_year: int | None = None
    production: float | None = None
    beginning_stocks: float | None = None
    imports: float | None = None
    domestic_total: float | None = None
    exports: float | None = None
    ending_stocks: float | None = None
    stock_to_use_pct: float | None = None
    unit: str = "1000 MT"
