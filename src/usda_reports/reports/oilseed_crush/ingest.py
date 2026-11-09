"""Fats & Oils ingest: the shared NASS ESMIS zip loop (:mod:`usda_reports.nass_common.ingest`)
configured for ``findByIdentifier/FatsOils`` from 2015-10-01.

A release whose ``files[]`` has no zip (2019-01-02: a reschedule notice) is recorded as
``skipped`` so it is not retried. Every zip is parsed and contract-checked (``check``) before
it reaches bronze; a problem raises :class:`NassError` and leaves bronze as it was.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from usda_reports.bronze.store import BronzeStore
from usda_reports.nass_common import ingest as nass_ingest
from usda_reports.nass_common.esmis import EsmisItem
from usda_reports.nass_common.ingest import IngestResult
from usda_reports.reports.oilseed_crush.source import NassError, SourceConfig

__all__ = ["IngestResult", "ingest", "releases"]


def releases(items: list[EsmisItem], cfg: SourceConfig) -> list[EsmisItem]:
    """ESMIS items from ``history_start`` on, oldest first, one per release date."""
    return nass_ingest.releases(items, cfg.history_start)


def ingest(
    client: httpx.Client,
    store: BronzeStore,
    cfg: SourceConfig,
    *,
    full: bool = False,
    force: bool = False,
    check: Callable[[str, bytes], None] | None = None,
    pause_s: float = 0.3,
) -> IngestResult:
    return nass_ingest.ingest_zips(
        client,
        store,
        cfg,
        title="Fats & Oils",
        log_prefix="crush",
        error=NassError,
        full=full,
        force=force,
        check=check,
        pause_s=pause_s,
    )
