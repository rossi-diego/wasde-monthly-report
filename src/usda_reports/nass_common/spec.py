"""Shared plumbing of every NASS ESMIS-zip report: stored releases, the silver writer and a
:class:`NassZipSpec` base that wires ingest, the pre-bronze check, the silver build and the
last-good fallback into the registry.

A concrete report (``oilseed_crush``, ``crop_progress``, ``grain_stocks``) provides its
``source.yaml`` model, a ``build_frame(releases, cfg, release_time_et)`` parser, a
``validate(silver, contract)`` check and its silver column list / Arrow schema.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from usda_reports.bronze.store import file_sha256
from usda_reports.core.logs import get_logger
from usda_reports.reports.base import ReportSpec

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.nass_common.ingest import IngestResult

log = get_logger(__name__)


@dataclass(frozen=True)
class StoredRelease:
    key: str
    sha256: str
    edition: int
    url: str | None
    data: bytes


def load_stored_releases(
    bronze_dir: Path,
    manifest: Manifest,
    report_id: str,
    error: type[Exception],
    strict: bool = True,
) -> list[StoredRelease]:
    """Every ok bronze entry of ``report_id`` in release order, sha256-verified.

    ``strict=False`` (the last-good fallback) stops at the first missing or altered file and
    returns the verified releases before it."""
    out = []
    for key, e in manifest.report(report_id).ok().items():
        assert e.file is not None
        path = bronze_dir / e.file
        if not path.exists() or file_sha256(path) != e.sha256:
            if not strict:
                log.error("silver.nass_bad_bronze", report=report_id, file=e.file)
                break
            raise error(f"bronze {e.file}: missing or sha256 mismatch")
        out.append(
            StoredRelease(
                key=key, sha256=str(e.sha256), edition=e.edition, url=e.url, data=path.read_bytes()
            )
        )
    return out


def arrow_schema(
    columns: list[str],
    *,
    ints: set[str] = frozenset(),  # type: ignore[assignment]
    floats: set[str] = frozenset(),  # type: ignore[assignment]
    dates: set[str] = frozenset(),  # type: ignore[assignment]
) -> pa.Schema:
    """Arrow schema of a NASS silver table: ``release_ts_utc`` is a UTC timestamp, the named
    columns int32 / float64 / date32, everything else a string."""

    def typ(c: str) -> pa.DataType:
        if c == "release_ts_utc":
            return pa.timestamp("ns", tz="UTC")
        if c in floats:
            return pa.float64()
        if c in dates:
            return pa.date32()
        if c in ints:
            return pa.int32()
        return pa.string()

    return pa.schema([(c, typ(c)) for c in columns])


def write_parquet(df: pd.DataFrame, columns: list[str], schema: pa.Schema, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df[columns], schema=schema, preserve_index=False)
    pq.write_table(table, path)
    return path


class NassZipSpec(ReportSpec):
    """Base spec of a NASS report published as zips on ESMIS.

    A problem in one NASS report must never block WASDE (and Soy Outlook's data-* release),
    Export Sales or the other NASS reports: every NASS report is isolated."""

    isolated = True
    #: Human name used in errors ("Crop Progress") and the log-event prefix ("crop_progress").
    title: ClassVar[str] = "NASS"
    log_prefix: ClassVar[str] = "nass"

    @property
    def source_path(self) -> Path:
        return self.config_dir / "source.yaml"

    @abstractmethod
    def source_config(self) -> Any:
        """The report's ``source.yaml`` model (esmis_url, history_start, recheck_last…)."""

    @abstractmethod
    def error_class(self) -> type[Exception]:
        """The report's own source error (raised on structural problems)."""

    @abstractmethod
    def silver_columns(self) -> list[str]: ...

    @abstractmethod
    def silver_schema(self) -> pa.Schema: ...

    @abstractmethod
    def frame(self, releases: list[StoredRelease]) -> pd.DataFrame:
        """Silver frame (envelope first) of ``releases``; raises on any parse problem."""

    @abstractmethod
    def validate(self, silver: pd.DataFrame) -> None:
        """Contract and report-specific checks; raises on a violation."""

    def source_errors(self) -> tuple[type[Exception], ...]:
        from usda_reports.core.contracts import ContractError
        from usda_reports.core.vocab import UnseenLabelError

        return (self.error_class(), UnseenLabelError, ContractError)

    def ingest(
        self,
        client: httpx.Client,
        store: BronzeStore,
        now: datetime | None = None,
        force: bool = False,
        full: bool = False,
    ) -> IngestResult:
        from usda_reports.nass_common.ingest import ingest_zips

        return ingest_zips(
            client,
            store,
            self.source_config(),
            title=self.title,
            log_prefix=self.log_prefix,
            error=self.error_class(),
            full=full,
            force=force,
            check=self.check_release,
        )

    def check_release(self, key: str, data: bytes) -> None:
        """Parse one downloaded zip on its own and run the silver contract on it."""
        rel = StoredRelease(key=key, sha256="0" * 64, edition=1, url=None, data=data)
        try:
            self._silver_from([rel])
        except self.source_errors() as exc:
            raise self.error_class()(f"release {key} rejected before bronze: {exc}") from exc

    def backfill(
        self, client: httpx.Client, store: BronzeStore, end: str, **kwargs: object
    ) -> list[str]:
        """Every missing release since ``history_start`` (all ESMIS pages)."""
        return self.ingest(client, store, full=True).ingested

    def _silver_from(self, releases: list[StoredRelease]) -> pd.DataFrame:
        silver = self.frame(releases)
        self.validate(silver)
        return silver

    def _write(self, silver: pd.DataFrame, releases: int) -> pd.DataFrame:
        write_parquet(silver, self.silver_columns(), self.silver_schema(), self.silver_path)
        log.info(f"silver.{self.log_prefix}", rows=len(silver), releases=releases)
        return silver

    def write_empty_silver(self) -> None:
        self._write(pd.DataFrame(columns=self.silver_columns()), 0)

    def load_releases(self, manifest: Manifest, strict: bool = True) -> list[StoredRelease]:
        return load_stored_releases(
            self.settings.bronze_dir, manifest, self.report_id, self.error_class(), strict
        )

    def build_silver(self, manifest: Manifest) -> pd.DataFrame:
        rels = self.load_releases(manifest)
        return self._write(self._silver_from(rels), len(rels))

    def build_silver_last_good(self, manifest: Manifest) -> pd.DataFrame:
        """Fallback after :meth:`build_silver` failed: keep the releases before the first one
        that fails on its own, then drop further newest releases until the rest builds; with
        nothing left, an empty silver with the full schema.

        Checking each release alone first keeps this linear for long weekly histories (Crop
        Progress has ~600 releases) instead of re-parsing everything once per dropped release."""
        try:
            rels = self.load_releases(manifest, strict=False)
        except Exception as exc:
            log.error(f"silver.{self.log_prefix}_unreadable", error=str(exc))
            rels = []
        for i, rel in enumerate(rels):
            try:
                self._silver_from([rel])
            except Exception as exc:
                log.warning(
                    f"silver.{self.log_prefix}_bad_release", release=rel.key, error=str(exc)
                )
                rels = rels[:i]
                break
        for keep in range(len(rels), 0, -1):
            try:
                silver = self._silver_from(rels[:keep])
            except Exception as exc:
                log.warning(f"silver.{self.log_prefix}_fallback", kept=keep, error=str(exc))
                continue
            log.warning(
                f"silver.{self.log_prefix}_last_good",
                kept=keep,
                dropped=[r.key for r in rels[keep:]],
            )
            return self._write(silver, keep)
        return self._write(pd.DataFrame(columns=self.silver_columns()), 0)
