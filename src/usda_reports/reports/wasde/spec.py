"""WASDE report spec: wires the existing WASDE ingest/parse code into the report registry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pandas as pd

from usda_reports.reports.base import ReportSpec

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest


class WasdeSpec(ReportSpec):
    """World Agricultural Supply and Demand Estimates (monthly, 12:00 ET)."""

    @property
    def unmapped_path(self) -> Path:
        return self.settings.silver_dir / "unmapped_labels.json"

    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        from usda_reports.reports.wasde.ingest import backfill

        seed_dir = kwargs.get("seed_dir")
        start = kwargs.get("start")
        return backfill(
            client,
            store,
            end,
            seed_dir if isinstance(seed_dir, Path) else None,
            start if isinstance(start, str) else None,  # None → USDA_HISTORY_START
        )

    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        from usda_reports.reports.wasde.silver import build_silver

        return build_silver(self.settings, manifest, self.config.release_time_et)

    def silver_alerts(self, silver: pd.DataFrame) -> list[str]:
        """Labels first seen in the newest report must be mapped before publishing."""
        from usda_reports.reports.wasde.silver import new_labels_in

        latest = str(silver["report_month"].max())
        return new_labels_in(self.unmapped_path, latest)
