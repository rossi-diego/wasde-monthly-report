"""Configuration and errors of the NASS Grain Stocks source.

Everything verified in the spike lives in ``config/reports/grain_stocks/source.yaml``: the
ESMIS identifier URL, the zip member, the title of the national summary table, the commodity
lines, date labels, position labels and units.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPORT_ID = "grain_stocks"
SOURCE = "esmis_zip"


class GrainStocksError(RuntimeError):
    """A Grain Stocks release (or its zip) cannot be used as published."""


class TableRef(BaseModel):
    title_prefix: str
    must_contain: str = ""
    header_first_cell: str = "Date"


class LagDays(BaseModel):
    min: int = 20
    max: int = 75


class SourceConfig(BaseModel):
    esmis_url: str
    zip_member: str = "*_all_tables.csv"
    history_start: str = "2010-06-30"
    recheck_last: int = 2
    table: TableRef
    release_lag_days: LagDays = Field(default_factory=LagDays)
    commodities: dict[str, str]
    known_groups: list[str] = Field(default_factory=list)
    date_labels: dict[str, int]
    positions: dict[str, str]
    units: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> SourceConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
