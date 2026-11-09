"""Export Sales report spec: wires the ESR ingest and silver parser into the registry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd

from usda_reports.core.calendar import load_calendar_raw
from usda_reports.core.logs import get_logger
from usda_reports.reports.base import ReportSpec

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.reports.export_sales.ingest import IngestResult
    from usda_reports.reports.export_sales.parse import Snapshot
    from usda_reports.reports.export_sales.source import SourceConfig

log = get_logger(__name__)


class ExportSalesSpec(ReportSpec):
    """U.S. Export Sales (weekly, Thursday 08:30 ET, FAS ESR API)."""

    # An ESR problem must never block WASDE (and Soy Outlook's data-* release).
    isolated = True

    @property
    def source_path(self) -> Path:
        return self.config_dir / "source.yaml"

    def source_config(self) -> SourceConfig:
        from usda_reports.reports.export_sales.source import SourceConfig

        return SourceConfig.load(self.source_path)

    def source_errors(self) -> tuple[type[Exception], ...]:
        from usda_reports.reports.export_sales.source import EsrError

        return (EsrError, *super().source_errors())

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
        return ingest(esr, store, now or datetime.now(UTC), force=force, check=self.check_bundle)

    def check_bundle(self, bundle: dict[str, Any]) -> None:
        """Parse one pulled bundle on its own and run the silver contract on it.

        Every destination code must resolve and the contract must hold *before* the pull is
        stored; otherwise :class:`EsrError` (so ``detect --report export_sales`` fails, the
        workflow opens the alert issue, and bronze keeps only good snapshots)."""
        from usda_reports.core.contracts import ContractError
        from usda_reports.core.vocab import UnseenLabelError
        from usda_reports.reports.export_sales.parse import Snapshot
        from usda_reports.reports.export_sales.source import EsrError

        snap = Snapshot(
            key=str(bundle["release_key"]), seq=1, sha256="0" * 64, edition=1, bundle=bundle
        )
        try:
            self._silver_from([snap])
        except (UnseenLabelError, ContractError) as exc:
            raise EsrError(f"release {snap.key} rejected before bronze: {exc}") from exc

    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        """Backfill when bronze is empty, otherwise pull the newest release if it is new."""
        return self.ingest(client, store).ingested

    def _silver_from(self, snaps: list[Snapshot]) -> pd.DataFrame:
        """Silver frame of ``snaps`` (pull order), contract-checked; raises on any problem."""
        from usda_reports.core.vocab import Vocab
        from usda_reports.reports.export_sales.parse import build_frame, my_start_months, validate

        cfg = self.source_config()
        silver = build_frame(
            snaps,
            cfg,
            Vocab.load(self.settings.config_dir / "vocab" / "countries.yaml"),
            my_start_months(self.settings.dbt_dir / "seeds" / "dim_commodity.csv"),
            load_calendar_raw(self.calendar_path),
            self.config.release_time_et,
        )
        validate(silver, self.contract(), cfg)
        return silver

    def _write(self, silver: pd.DataFrame, snapshots: int) -> pd.DataFrame:
        from usda_reports.reports.export_sales.parse import write_silver

        self.settings.silver_dir.mkdir(parents=True, exist_ok=True)
        write_silver(silver, self.silver_path)
        log.info(
            "silver.export_sales",
            rows=len(silver),
            snapshots=snapshots,
            releases=int(silver["release_key"].nunique()) if len(silver) else 0,
        )
        return silver

    def write_empty_silver(self) -> None:
        from usda_reports.reports.export_sales.parse import SILVER_COLUMNS

        self._write(pd.DataFrame(columns=SILVER_COLUMNS), 0)

    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        from usda_reports.reports.export_sales.parse import load_snapshots

        snaps = load_snapshots(self.settings.bronze_dir, manifest)
        return self._write(self._silver_from(snaps), len(snaps))

    def build_silver_last_good(self, manifest: Manifest) -> pd.DataFrame:
        """Fallback after :meth:`build_silver` failed: drop the newest snapshot(s) until the
        rest builds (the last good state); with nothing left, an empty silver with the full
        schema, so WASDE gold and publish still run."""
        from usda_reports.reports.export_sales.parse import SILVER_COLUMNS, load_snapshots

        try:
            snaps = load_snapshots(self.settings.bronze_dir, manifest)
        except Exception as exc:
            log.error("silver.export_sales_unreadable", error=str(exc))
            snaps = []
        for keep in range(len(snaps) - 1, 0, -1):
            try:
                silver = self._silver_from(snaps[:keep])
            except Exception as exc:
                log.warning("silver.export_sales_fallback", kept=keep, error=str(exc))
                continue
            log.warning(
                "silver.export_sales_last_good",
                kept=keep,
                dropped=[s.key for s in snaps[keep:]],
            )
            return self._write(silver, keep)
        return self._write(pd.DataFrame(columns=SILVER_COLUMNS), 0)
