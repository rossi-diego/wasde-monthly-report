"""Export Sales report spec: wires the ESR ingest and silver parser into the registry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pandas as pd

from usda_reports.core.calendar import load_calendar_raw
from usda_reports.core.logs import get_logger
from usda_reports.reports.base import ReportSpec

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.reports.export_sales.ingest import IngestResult
    from usda_reports.reports.export_sales.source import SourceConfig

log = get_logger(__name__)


class ExportSalesSpec(ReportSpec):
    """U.S. Export Sales (weekly, Thursday 08:30 ET, FAS ESR API)."""

    @property
    def source_path(self) -> Path:
        return self.config_dir / "source.yaml"

    def source_config(self) -> SourceConfig:
        from usda_reports.reports.export_sales.source import SourceConfig

        return SourceConfig.load(self.source_path)

    def esr_client(self, client: httpx.Client) -> object:
        from usda_reports.reports.export_sales.source import EsrClient

        cfg = self.source_config()
        # Settings also reads .env (FAS_API_KEY, then USDA_PSD_KEY); the key is never logged.
        key = self.settings.fas_api_key
        return EsrClient(client, cfg, key.get_secret_value() if key else cfg.api_key())

    def ingest(
        self,
        client: httpx.Client,
        store: BronzeStore,
        now: datetime | None = None,
        force: bool = False,
    ) -> IngestResult:
        from usda_reports.reports.export_sales.ingest import ingest
        from usda_reports.reports.export_sales.source import EsrClient

        esr = self.esr_client(client)
        assert isinstance(esr, EsrClient)
        return ingest(esr, store, now or datetime.now(UTC), force=force)

    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        """Backfill when bronze is empty, otherwise pull the newest release if it is new."""
        return self.ingest(client, store).ingested

    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        from usda_reports.core.vocab import Vocab
        from usda_reports.reports.export_sales.parse import (
            build_frame,
            load_snapshots,
            my_start_months,
            validate,
            write_silver,
        )

        cfg = self.source_config()
        snaps = load_snapshots(self.settings.bronze_dir, manifest)
        silver = build_frame(
            snaps,
            cfg,
            Vocab.load(self.settings.config_dir / "vocab" / "countries.yaml"),
            my_start_months(self.settings.dbt_dir / "seeds" / "dim_commodity.csv"),
            load_calendar_raw(self.calendar_path),
            self.config.release_time_et,
        )
        validate(silver, self.contract(), cfg)
        self.settings.silver_dir.mkdir(parents=True, exist_ok=True)
        write_silver(silver, self.silver_path)
        log.info(
            "silver.export_sales",
            rows=len(silver),
            snapshots=len(snaps),
            releases=int(silver["release_key"].nunique()) if len(silver) else 0,
        )
        return silver
