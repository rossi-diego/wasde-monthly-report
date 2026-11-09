"""WASDE ingestion into bronze: USDA CSV (2021+) and ESMIS XML (2010-07+, plus local seeds)."""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from usda_reports.bronze.store import BronzeStore
from usda_reports.core.config import get_settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import ReleaseEntry
from usda_reports.core.net import get
from usda_reports.reports.wasde.sources.esmis import EsmisRelease, list_releases
from usda_reports.reports.wasde.sources.usda_csv import CSV_FIRST_MONTH, csv_url, fetch_csv

log = get_logger(__name__)


def looks_like_xml(data: bytes) -> bool:
    """True for an XML document (tolerates a UTF-8 BOM); False for HTML error pages."""
    head = data.lstrip(b"\xef\xbb\xbf \r\n\t")[:200].lower()
    return head.startswith(b"<?xml") or (
        head.startswith(b"<") and not head.startswith(b"<!doctype html") and b"<html" not in head
    )


def month_range(start: str, end: str) -> list[str]:
    y, m = (int(p) for p in start.split("-"))
    ey, em = (int(p) for p in end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ── Local seed files (owner's historical ESMIS downloads) ────────────────────

_SEED_RE = re.compile(r"^(\d{4}-\d{2})-(\d{2})_(.+)\.xml$", re.IGNORECASE)


def find_seed_files(seed_dir: Path) -> dict[str, Path]:
    """Map ``YYYY-MM`` -> best local XML (skip ORIG drafts, prefer v2, then latest day)."""
    best: dict[str, tuple[tuple[int, str], Path]] = {}
    for p in sorted(seed_dir.glob("*.xml")):
        m = _SEED_RE.match(p.name)
        if not m or "orig" in m.group(3).lower():
            continue
        month, day, stem = m.groups()
        version = 2 if re.search(r"v\d$", stem, re.IGNORECASE) else 1
        rank = (version, day)
        if month not in best or rank > best[month][0]:
            best[month] = (rank, p)
    return {k: v[1] for k, v in sorted(best.items())}


def ingest_month(
    client: httpx.Client,
    store: BronzeStore,
    month: str,
    esmis: dict[str, EsmisRelease] | None,
    seeds: dict[str, Path] | None = None,
    version: int | None = None,
) -> ReleaseEntry | None:
    """Fetch one report. CSV first (2021+), then ESMIS XML (local seed, then download)."""
    rel = (esmis or {}).get(month)
    if month >= CSV_FIRST_MONTH:
        body = fetch_csv(client, month)
        if body is not None:
            return store.put(
                month,
                body,
                source="usda_csv",
                url=csv_url(month),
                release_date=rel.release_date.isoformat() if rel else None,
                edition=version or (rel.version if rel else 1),
            )
    if seeds and month in seeds:
        data = seeds[month].read_bytes()
        url = rel.xml_url if rel else f"file://{seeds[month].name}"
        return store.put(
            month,
            data,
            source="esmis_xml",
            url=url,
            release_date=rel.release_date.isoformat() if rel else seeds[month].name[:10],
            edition=rel.version if rel else 1,
        )
    if rel is None:
        log.warning("bronze.unavailable", month=month)
        return None
    resp = get(client, rel.xml_url)
    if resp is None or not looks_like_xml(resp.content):
        log.warning("bronze.xml_missing", month=month, url=rel.xml_url)
        return None
    return store.put(
        month,
        resp.content,
        source="esmis_xml",
        url=rel.xml_url,
        release_date=rel.release_date.isoformat(),
        edition=rel.version,
    )


def backfill(
    client: httpx.Client,
    store: BronzeStore,
    end_month: str,
    seed_dir: Path | None = None,
    start_month: str | None = None,
) -> list[str]:
    """Ingest every report month in range that is not yet in the manifest."""
    start = start_month or get_settings().history_start
    esmis = list_releases(client)
    seeds = find_seed_files(seed_dir) if seed_dir and seed_dir.exists() else None
    wanted = [m for m in month_range(start, end_month) if m not in store.entries]
    new: list[str] = []
    for month in wanted:
        if month < CSV_FIRST_MONTH and month not in esmis and not (seeds and month in seeds):
            continue  # no report that month (e.g. 2013-10 shutdown, 2019-01)
        if ingest_month(client, store, month, esmis, seeds):
            new.append(month)
    log.info("bronze.backfill_done", requested=len(wanted), ingested=len(new))
    return new
