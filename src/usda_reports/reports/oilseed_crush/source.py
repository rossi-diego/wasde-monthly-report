"""Configuration and errors of the NASS Fats & Oils (oilseed crush) source.

Everything that was verified in the spike lives in ``config/reports/oilseed_crush/source.yaml``:
the ESMIS identifier URL, the zip member, the title of the soybean table, the unit labels and
the row labels mapped to silver metrics.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPORT_ID = "oilseed_crush"
SOURCE = "esmis_zip"


class NassError(RuntimeError):
    """A Fats & Oils release (or its zip) cannot be used as published."""


class MetricRef(BaseModel):
    metric: str
    unit: str
    commodity_id: str


class TableRef(BaseModel):
    title_prefix: str
    number: str
    header_first_cell: str = "Item"


class LagMonths(BaseModel):
    min: int = 1
    max: int = 3


class SourceConfig(BaseModel):
    esmis_url: str
    zip_member: str = "*_all_tables.csv"
    history_start: str = "2015-10-01"
    recheck_last: int = 2
    lag_months: LagMonths = Field(default_factory=LagMonths)
    table: TableRef
    header_fixes: dict[str, dict[str, str]] = Field(default_factory=dict)
    oilseed: str = "soybeans"
    units: dict[str, str]
    metrics: dict[str, MetricRef]
    known_rows: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> SourceConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
