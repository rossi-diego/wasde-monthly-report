# src/wasde/models/wasde.py
"""Pydantic models for WASDE CSV data."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class WASDERecord(BaseModel):
    """Validated WASDE supply & demand record (Silver layer)."""

    wasde_number: int
    forecast_year: int
    forecast_month: int
    report_title: str
    commodity: str
    region: str
    marketing_year: str
    marketing_year_start: int
    attribute: str
    value: float | None
    unit: str
    release_date: date
    proj_est_flag: str
    annual_quarter_flag: str

    @field_validator(
        "report_title",
        "commodity",
        "region",
        "attribute",
        "unit",
        "proj_est_flag",
        "annual_quarter_flag",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, v: object) -> str:
        return str(v).strip()


class WASDERevisionResponse(BaseModel):
    """API response model for WASDE revision tracking."""

    commodity: str
    region: str
    marketing_year: str
    attribute: str
    unit: str
    forecast_year: int
    forecast_month: int
    value: float
    prev_value: float | None
    mom_change: float | None
    first_estimate: float | None
    cumulative_revision: float | None
    revision_number: int


class WASDELatestResponse(BaseModel):
    """API response model for latest WASDE S&D balance sheet."""

    commodity: str
    region: str
    marketing_year: str
    marketing_year_start: int
    unit: str
    latest_report_year: int
    latest_report_month: int
    production: float | None
    beginning_stocks: float | None
    imports: float | None
    exports: float | None
    ending_stocks: float | None
    domestic_use: float | None
    total_supply: float | None
