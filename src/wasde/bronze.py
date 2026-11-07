"""Bronze layer: raw upstream files stored byte-for-byte, plus provenance in the manifest."""

from __future__ import annotations

import hashlib
import re
import shutil
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from wasde.config import get_settings
from wasde.logs import get_logger
from wasde.manifest import Manifest, ReportEntry
from wasde.net import get
from wasde.sources.esmis import EsmisRelease, list_releases
from wasde.sources.usda_csv import CSV_FIRST_MONTH, csv_url, fetch_csv

log = get_logger(__name__)

CSV_DIR = "usda_csv"
XML_DIR = "esmis_xml"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def looks_like_xml(data: bytes) -> bool:
    """True for an XML document (tolerates a UTF-8 BOM); False for HTML error pages."""
    head = data.lstrip(b"\xef\xbb\xbf \r\n\t")[:200].lower()
    return head.startswith(b"<?xml") or (head.startswith(b"<") and not head.startswith(b"<!doctype html") and b"<html" not in head)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


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


# ── Store ────────────────────────────────────────────────────────────────────


@dataclass
class BronzeStore:
    root: Path
    manifest: Manifest

    def path_for(self, entry: ReportEntry) -> Path:
        return self.root / entry.file

    def put(
        self,
        month: str,
        data: bytes,
        *,
        source: str,
        url: str,
        release_date: str | None = None,
        version: int = 1,
    ) -> ReportEntry:
        sub, ext = (CSV_DIR, "csv") if source == "usda_csv" else (XML_DIR, "xml")
        rel = f"{sub}/{month}.{ext}"
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = ReportEntry(
            source=source,
            file=rel,
            url=url,
            sha256=sha256(data),
            bytes=len(data),
            release_date=release_date,
            version=version,
            fetched_at=_now(),
        )
        self.manifest.reports[month] = entry
        log.info("bronze.stored", month=month, source=source, bytes=len(data))
        return entry

    def verify(self) -> list[str]:
        """Return months whose file is missing or whose hash no longer matches."""
        bad = []
        for month, e in self.manifest.reports.items():
            p = self.path_for(e)
            if not p.exists() or sha256(p.read_bytes()) != e.sha256:
                bad.append(month)
        return bad


def ingest_month(
    client: httpx.Client,
    store: BronzeStore,
    month: str,
    esmis: dict[str, EsmisRelease] | None,
    seeds: dict[str, Path] | None = None,
) -> ReportEntry | None:
    """Fetch one report. CSV first (2021+), then ESMIS XML (local seed, then download)."""
    if month >= CSV_FIRST_MONTH:
        body = fetch_csv(client, month)
        if body is not None:
            return store.put(month, body, source="usda_csv", url=csv_url(month))
    rel = (esmis or {}).get(month)
    if seeds and month in seeds:
        data = seeds[month].read_bytes()
        url = rel.xml_url if rel else f"file://{seeds[month].name}"
        return store.put(
            month,
            data,
            source="esmis_xml",
            url=url,
            release_date=rel.release_date.isoformat() if rel else seeds[month].name[:10],
            version=rel.version if rel else 1,
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
        version=rel.version,
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
    wanted = [m for m in month_range(start, end_month) if m not in store.manifest.reports]
    new: list[str] = []
    for month in wanted:
        if month < CSV_FIRST_MONTH and month not in esmis and not (seeds and month in seeds):
            continue  # no report that month (e.g. 2013-10 shutdown, 2019-01)
        if ingest_month(client, store, month, esmis, seeds):
            new.append(month)
    log.info("bronze.backfill_done", requested=len(wanted), ingested=len(new))
    return new


# ── Archive (GitHub release asset) ───────────────────────────────────────────


def pack(root: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz", compresslevel=6) as tar:
        for sub in (CSV_DIR, XML_DIR):
            if (root / sub).exists():
                tar.add(root / sub, arcname=sub)
    log.info("bronze.packed", path=str(out), bytes=out.stat().st_size)
    return out


def unpack(archive: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(root, filter="data")
    log.info("bronze.unpacked", path=str(archive))


def reset(root: Path) -> None:
    for sub in (CSV_DIR, XML_DIR):
        shutil.rmtree(root / sub, ignore_errors=True)
