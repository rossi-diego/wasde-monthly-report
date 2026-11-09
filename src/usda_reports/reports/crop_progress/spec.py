"""Crop Progress report spec: the shared NASS ESMIS-zip plumbing configured for CropProg."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa

from usda_reports.nass_common.spec import NassZipSpec

if TYPE_CHECKING:
    from usda_reports.nass_common.spec import StoredRelease
    from usda_reports.reports.crop_progress.source import SourceConfig


class CropProgressSpec(NassZipSpec):
    """NASS Crop Progress (weekly, Monday 16:00 ET, April-November; national rows only)."""

    title = "Crop Progress"
    log_prefix = "crop_progress"

    def source_config(self) -> SourceConfig:
        from usda_reports.reports.crop_progress.source import SourceConfig

        return SourceConfig.load(self.source_path)

    def error_class(self) -> type[Exception]:
        from usda_reports.reports.crop_progress.source import CropProgressError

        return CropProgressError

    def silver_columns(self) -> list[str]:
        from usda_reports.reports.crop_progress.parse import SILVER_COLUMNS

        return SILVER_COLUMNS

    def silver_schema(self) -> pa.Schema:
        from usda_reports.reports.crop_progress.parse import SILVER_SCHEMA

        return SILVER_SCHEMA

    def frame(self, releases: list[StoredRelease]) -> pd.DataFrame:
        from usda_reports.reports.crop_progress.parse import build_frame

        return build_frame(releases, self.source_config(), self.config.release_time_et)

    def validate(self, silver: pd.DataFrame) -> None:
        from usda_reports.reports.crop_progress.parse import validate

        validate(silver, self.contract())
