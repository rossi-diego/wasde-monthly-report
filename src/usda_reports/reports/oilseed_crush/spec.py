"""Oilseed crush report spec: wires the Fats & Oils ingest and silver parser into the registry
(through the shared :class:`~usda_reports.nass_common.spec.NassZipSpec`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa

from usda_reports.nass_common.spec import NassZipSpec

if TYPE_CHECKING:
    from usda_reports.nass_common.spec import StoredRelease
    from usda_reports.reports.oilseed_crush.source import SourceConfig


class OilseedCrushSpec(NassZipSpec):
    """NASS Fats & Oils (monthly, ~1st business day 15:00 ET, covering month − 2)."""

    title = "Fats & Oils"
    log_prefix = "crush"

    def source_config(self) -> SourceConfig:
        from usda_reports.reports.oilseed_crush.source import SourceConfig

        return SourceConfig.load(self.source_path)

    def error_class(self) -> type[Exception]:
        from usda_reports.reports.oilseed_crush.source import NassError

        return NassError

    def silver_columns(self) -> list[str]:
        from usda_reports.reports.oilseed_crush.parse import SILVER_COLUMNS

        return SILVER_COLUMNS

    def silver_schema(self) -> pa.Schema:
        from usda_reports.reports.oilseed_crush.parse import SILVER_SCHEMA

        return SILVER_SCHEMA

    def frame(self, releases: list[StoredRelease]) -> pd.DataFrame:
        from usda_reports.reports.oilseed_crush.parse import build_frame

        return build_frame(releases, self.source_config(), self.config.release_time_et)

    def validate(self, silver: pd.DataFrame) -> None:
        from usda_reports.reports.oilseed_crush.parse import validate

        validate(silver, self.contract())
