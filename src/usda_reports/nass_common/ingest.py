"""Generic ESMIS zip ingest shared by every NASS report (Fats & Oils, Crop Progress, Grain
Stocks): list ESMIS releases, download each zip from ``files[]`` into bronze.

* **Backfill** (no release of the report in the manifest yet, or ``full=True``): every ESMIS
  page from page 0, every release from ``history_start``.
* **Regular run**: page 0 only (the newest 25 releases): new releases are stored, and the
  newest ``recheck_last`` stored releases are downloaded again; changed bytes become a new
  edition of the same release key.
* A release whose ``files[]`` has no zip (a reschedule notice, a text-only correction, or a
  release whose zip is attached minutes after its PDF/TXT) is recorded as ``skipped``. Skipped
  releases are looked at again on every later run: once a zip shows up in ``files[]`` it is
  downloaded and stored as edition 1 (plan §11: a late posting is caught by the next run).
* A release date listed more than once (ESMIS re-posts, e.g. Grain Stocks 2025-09-30 three
  times) keeps the highest ESMIS id.

Every zip is parsed and contract-checked (``check``) *before* it reaches bronze; a problem
raises the report's own error (or an unseen-label error) and leaves bronze as it was.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from usda_reports.bronze.store import BronzeStore, sha256
from usda_reports.core.logs import get_logger
from usda_reports.nass_common.esmis import EsmisItem, fetch_items
from usda_reports.nass_common.zipfetch import NassZipError, fetch_zip

log = get_logger(__name__)

SOURCE = "esmis_zip"
ALL_PAGES = 60


class EsmisZipConfig(Protocol):
    """What the generic ingest needs from a report's ``source.yaml`` model."""

    esmis_url: str
    history_start: str
    recheck_last: int


@dataclass
class IngestResult:
    ingested: list[str] = field(default_factory=list)  # release keys new or changed in bronze
    skipped: list[str] = field(default_factory=list)  # releases without a zip
    note: str = ""
    calls: int = 0


def releases(items: list[EsmisItem], history_start: str) -> list[EsmisItem]:
    """ESMIS items from ``history_start`` on, oldest first, one per release date (the
    highest ESMIS id wins if a date is listed twice)."""
    best: dict[str, EsmisItem] = {}
    for it in items:
        if it.release_key < history_start:
            continue
        cur = best.get(it.release_key)
        if cur is None or int(it.release_id or 0) > int(cur.release_id or 0):
            best[it.release_key] = it
    return [best[k] for k in sorted(best)]


def ingest_zips(
    client: httpx.Client,
    store: BronzeStore,
    cfg: EsmisZipConfig,
    *,
    title: str,
    log_prefix: str,
    error: type[Exception],
    full: bool = False,
    force: bool = False,
    check: Callable[[str, bytes], None] | None = None,
    pause_s: float = 0.3,
) -> IngestResult:
    """Store every new (or changed) release zip of one NASS report in bronze.

    ``title`` names the report in errors, ``log_prefix`` its log events (``crush.ingest``…),
    ``error`` is the report's own source error class."""
    result = IngestResult()
    ok = {k for k, e in store.entries.items() if e.status == "ok"}
    every_page = full or not ok
    items = releases(
        fetch_items(client, cfg.esmis_url, ALL_PAGES if every_page else 1), cfg.history_start
    )
    result.calls += 1
    if not items:
        raise error(f"ESMIS listed no {title} release since {cfg.history_start}")
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
                log.warning(f"{log_prefix}.no_zip", release=key, files=names)
            continue
        if old is not None and not force and old.status == "ok" and key not in recheck:
            continue
        if old is not None and old.status != "ok":
            log.info(f"{log_prefix}.zip_appeared", release=key, url=url)
        try:
            data = fetch_zip(client, url)
        except NassZipError as exc:
            raise error(f"release {key}: {exc}") from exc
        result.calls += 1
        if pause_s:
            time.sleep(pause_s)
        if data is None:
            log.warning(f"{log_prefix}.zip_missing", release=key, url=url)
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
        f"{log_prefix}.ingest",
        listed=len(items),
        ingested=result.ingested,
        skipped=result.skipped,
        every_page=every_page,
        calls=result.calls,
    )
    return result
