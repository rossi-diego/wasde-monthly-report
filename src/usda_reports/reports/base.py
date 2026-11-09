"""Report abstraction shared by every USDA report.

A report plugs into the pipeline by providing a :class:`ReportSpec` (registered in
``config/reports.yaml``). The pipeline only talks to specs; report-specific parsing,
vocabularies and contracts stay inside ``reports/<report_id>/``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pandas as pd

from usda_reports.core.calendar import load_calendar
from usda_reports.core.contracts import Contract

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.config import Settings
    from usda_reports.core.manifest import Manifest
    from usda_reports.core.registry import ReportConfig


@dataclass(frozen=True)
class Release:
    """One publication of one report, as discovered upstream."""

    report_id: str
    release_key: str  # e.g. "2026-10" (monthly) or "2026-11-06" (weekly)
    release_ts_utc: datetime | None
    edition: int = 1
    url: str | None = None
    source: str | None = None


class ReportSpec(ABC):
    """What the pipeline needs from a report: ingest into bronze and build silver."""

    def __init__(self, settings: Settings, config: ReportConfig) -> None:
        self.settings = settings
        self.config = config

    @property
    def report_id(self) -> str:
        return self.config.id

    @property
    def config_dir(self) -> Path:
        return self.settings.report_config_dir(self.report_id)

    @property
    def calendar_path(self) -> Path:
        return self.settings.calendars_dir / f"{self.report_id}.yaml"

    @property
    def silver_path(self) -> Path:
        return self.settings.silver_dir / f"{self.report_id}.parquet"

    def calendar(self) -> list[date]:
        return load_calendar(self.calendar_path)

    def contract(self) -> Contract:
        return Contract.load(self.settings.config_dir / "contracts" / f"{self.report_id}.yaml")

    @abstractmethod
    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        """Ingest every missing release up to ``end``; return the new release keys."""

    @abstractmethod
    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        """Full reparse of bronze into ``data/silver/<report_id>.parquet`` (envelope included)."""

    def silver_alerts(self, silver: pd.DataFrame) -> list[str]:
        """Problems that must fail the run after silver was written (e.g. new labels)."""
        return []
