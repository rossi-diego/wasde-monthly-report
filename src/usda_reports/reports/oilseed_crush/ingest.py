"""Fats & Oils ingest: list ESMIS releases, download each zip from ``files[]`` into bronze.

* **Backfill** (no crush release in the manifest yet, or ``full=True``): every ESMIS page from
  page 0, every release from ``history_start`` (2015-10-01).
* **Regular run**: page 0 only (the newest 25 releases): new releases are stored, and the
  newest ``recheck_last`` stored releases are downloaded again; changed bytes become a new
  edition of the same release key.
* A release whose ``files[]`` has no zip (2019-01-02: a reschedule notice) is recorded as
  ``skipped`` so it is not retried.

Every zip is parsed and contract-checked (``check``) *before* it reaches bronze; a problem
raises :class:`NassError` (or an unseen-label error) and leaves bronze as it was.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from usda_reports.bronze.store import BronzeStore, sha256
from usda_reports.core.logs import get_logger
from usda_reports.nass_common.esmis import EsmisItem, fetch_items
from usda_reports.nass_common.zipfetch import NassZipError, fetch_zip
from usda_reports.reports.oilseed_crush.source import SOURCE, NassError, SourceConfig

log = get_logger(__name__)


@dataclass
class IngestResult:
    ingested: list[str] = field(default_factory=list)  # release keys new or changed in bronze
    skipped: list[str] = field(default_factory=list)  # releases without a zip
    note: str = ""
    calls: int = 0


def releases(items: list[EsmisItem], cfg: SourceConfig) -> list[EsmisItem]:
    """ESMIS items from ``history_start`` on, oldest first, one per release date (the
    highest ESMIS id wins if a date is listed twice)."""
    best: dict[str, EsmisItem] = {}
    for it in items:
        if it.release_key < cfg.history_start:
            continue
        cur = best.get(it.release_key)
        if cur is None or int(it.release_id or 0) > int(cur.release_id or 0):
            best[it.release_key] = it
    return [best[k] for k in sorted(best)]


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
    result = IngestResult()
    ok = {k for k, e in store.entries.items() if e.status == "ok"}
    every_page = full or not ok
    items = releases(fetch_items(client, cfg.esmis_url, 60 if every_page else 1), cfg)
    result.calls += 1
    if not items:
        raise NassError(f"ESMIS listed no Fats & Oils release since {cfg.history_start}")
    recheck = set(sorted(ok)[-cfg.recheck_last :]) if cfg.recheck_last else set()
    for it in items:
        key = it.release_key
        old = store.entries.get(key)
        url = it.file_with_suffix(".zip")
        if url is None:
            if old is None:
                names = ", ".join(f.rsplit("/", 1)[-1] for f in it.files) or "none"
                store.skip(key, SOURCE, f"no zip in ESMIS files[] (files: {names})")
                result.skipped.append(key)
                log.warning("crush.no_zip", release=key, files=names)
            continue
        if old is not None and not force and (old.status != "ok" or key not in recheck):
            continue
        try:
            data = fetch_zip(client, url)
        except NassZipError as exc:
            raise NassError(f"release {key}: {exc}") from exc
        result.calls += 1
        if pause_s:
            time.sleep(pause_s)
        if data is None:
            log.warning("crush.zip_missing", release=key, url=url)
            continue
        if old is not None and old.status == "ok" and old.sha256 == sha256(data):
            continue
        if check is not None:
            check(key, data)  # raises: nothing is written to bronze
        edition = old.edition + 1 if old is not None and old.status == "ok" else 1
        store.put(key, data, source=SOURCE, url=url, release_date=key, edition=edition)
        result.ingested.append(key)
    result.note = "ingested" if result.ingested else "no new release"
    log.info(
        "crush.ingest",
        listed=len(items),
        ingested=result.ingested,
        skipped=result.skipped,
        every_page=every_page,
        calls=result.calls,
    )
    return result
