"""Oilseed crush report spec: wires the Fats & Oils ingest and silver parser into the registry."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pandas as pd

from usda_reports.core.logs import get_logger
from usda_reports.reports.base import ReportSpec

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.reports.oilseed_crush.ingest import IngestResult
    from usda_reports.reports.oilseed_crush.parse import StoredRelease
    from usda_reports.reports.oilseed_crush.source import SourceConfig

log = get_logger(__name__)


class OilseedCrushSpec(ReportSpec):
    """NASS Fats & Oils (monthly, ~1st business day 15:00 ET, covering month − 2)."""

    # A crush problem must never block WASDE (and Soy Outlook's data-* release) or ESR.
    isolated = True

    @property
    def source_path(self) -> Path:
        return self.config_dir / "source.yaml"

    def source_config(self) -> SourceConfig:
        from usda_reports.reports.oilseed_crush.source import SourceConfig

        return SourceConfig.load(self.source_path)

    def source_errors(self) -> tuple[type[Exception], ...]:
        from usda_reports.core.contracts import ContractError
        from usda_reports.core.vocab import UnseenLabelError
        from usda_reports.reports.oilseed_crush.source import NassError

        return (NassError, UnseenLabelError, ContractError)

    def ingest(
        self,
        client: httpx.Client,
        store: BronzeStore,
        now: datetime | None = None,
        force: bool = False,
        full: bool = False,
    ) -> IngestResult:
        from usda_reports.reports.oilseed_crush.ingest import ingest

        return ingest(
            client, store, self.source_config(), full=full, force=force, check=self.check_release
        )

    def check_release(self, key: str, data: bytes) -> None:
        """Parse one downloaded zip on its own and run the silver contract on it."""
        from usda_reports.reports.oilseed_crush.parse import StoredRelease
        from usda_reports.reports.oilseed_crush.source import NassError

        rel = StoredRelease(key=key, sha256="0" * 64, edition=1, url=None, data=data)
        try:
            self._silver_from([rel])
        except self.source_errors() as exc:
            raise NassError(f"release {key} rejected before bronze: {exc}") from exc

    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        """Every missing release since 2015-10 (all ESMIS pages)."""
        return self.ingest(client, store, full=True).ingested

    def _silver_from(self, releases: list[StoredRelease]) -> pd.DataFrame:
        from usda_reports.reports.oilseed_crush.parse import build_frame, validate

        silver = build_frame(releases, self.source_config(), self.config.release_time_et)
        validate(silver, self.contract())
        return silver

    def _write(self, silver: pd.DataFrame, releases: int) -> pd.DataFrame:
        from usda_reports.reports.oilseed_crush.parse import write_silver

        write_silver(silver, self.silver_path)
        log.info("silver.oilseed_crush", rows=len(silver), releases=releases)
        return silver

    def write_empty_silver(self) -> None:
        from usda_reports.reports.oilseed_crush.parse import SILVER_COLUMNS

        self._write(pd.DataFrame(columns=SILVER_COLUMNS), 0)

    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        from usda_reports.reports.oilseed_crush.parse import load_releases

        rels = load_releases(self.settings.bronze_dir, manifest)
        return self._write(self._silver_from(rels), len(rels))

    def build_silver_last_good(self, manifest: Manifest) -> pd.DataFrame:
        """Fallback after :meth:`build_silver` failed: drop the newest release(s) until the rest
        builds; with nothing left, an empty silver with the full schema."""
        from usda_reports.reports.oilseed_crush.parse import SILVER_COLUMNS, load_releases

        try:
            rels = load_releases(self.settings.bronze_dir, manifest, strict=False)
        except Exception as exc:
            log.error("silver.oilseed_crush_unreadable", error=str(exc))
            rels = []
        for keep in range(len(rels), 0, -1):
            try:
                silver = self._silver_from(rels[:keep])
            except Exception as exc:
                log.warning("silver.oilseed_crush_fallback", kept=keep, error=str(exc))
                continue
            log.warning(
                "silver.oilseed_crush_last_good", kept=keep, dropped=[r.key for r in rels[keep:]]
            )
            return self._write(silver, keep)
        return self._write(pd.DataFrame(columns=SILVER_COLUMNS), 0)
