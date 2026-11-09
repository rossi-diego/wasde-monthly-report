"""Configuration and errors of the NASS Crop Progress source.

Everything verified in the spike lives in ``config/reports/crop_progress/source.yaml``: the
ESMIS identifier URL, the zip member, the crops kept, the stage and condition labels and the
national-row pattern.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPORT_ID = "crop_progress"
SOURCE = "esmis_zip"


class CropProgressError(RuntimeError):
    """A Crop Progress release (or its zip) cannot be used as published."""


class CropRef(BaseModel):
    commodity_id: str
    title_names: list[str]


class LagDays(BaseModel):
    min: int = 1
    max: int = 4


class SourceConfig(BaseModel):
    esmis_url: str
    zip_member: str = "*_all_tables.csv"
    history_start: str = "2010-06-07"
    recheck_last: int = 2
    release_lag_days: LagDays = Field(default_factory=LagDays)
    crops: dict[str, CropRef]
    stages: dict[str, dict[str, str]]
    condition_word: str = "Condition"
    conditions: dict[str, str]
    condition_rows: dict[str, str]
    total_row_pattern: str
    unit_labels: list[str]

    @classmethod
    def load(cls, path: Path) -> SourceConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def stage_order(self, crop: str) -> list[str]:
        """Categories of ``crop`` in crop-calendar order."""
        return list(self.stages[crop].values())
