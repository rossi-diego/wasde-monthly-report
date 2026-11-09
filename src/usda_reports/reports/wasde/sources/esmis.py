"""ESMIS index of historical WASDE files (built on :mod:`usda_reports.nass_common.esmis`).

File URLs before 2025 are not predictable, so they must come from the API.
WASDE-specific caveats handled here: a month can have several releases (revised ``v2``
editions, odd one-offs), and some releases have no XML (pre 2010-07: PDF/TXT only).
The generic client handles 0-based paging, unsorted results and the dummy 12:00Z times.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from usda_reports.core.config import get_settings
from usda_reports.core.logs import get_logger
from usda_reports.nass_common.esmis import EsmisItem, fetch_items, parse_items

log = get_logger(__name__)

_VERSION_RE = re.compile(r"v(\d+)\.xml$", re.IGNORECASE)


@dataclass(frozen=True)
class EsmisRelease:
    release_id: str
    release_date: date
    xml_url: str

    @property
    def report_month(self) -> str:
        return f"{self.release_date:%Y-%m}"

    @property
    def version(self) -> int:
        m = _VERSION_RE.search(self.xml_url)
        return int(m.group(1)) if m else 1


def _with_xml(items: list[EsmisItem]) -> list[EsmisRelease]:
    out = []
    for it in items:
        xml = it.file_with_suffix(".xml")
        if xml:
            out.append(EsmisRelease(it.release_id, it.release_date, xml))
    return out


def parse_releases(payload: dict[str, Any]) -> list[EsmisRelease]:
    """Parse one API page into releases that carry an XML file."""
    return _with_xml(parse_items(payload))


def latest_per_month(releases: list[EsmisRelease]) -> dict[str, EsmisRelease]:
    """Keep one release per report month: highest version, then latest date."""
    best: dict[str, EsmisRelease] = {}
    for r in releases:
        cur = best.get(r.report_month)
        if cur is None or (r.version, r.release_date) > (cur.version, cur.release_date):
            best[r.report_month] = r
    return dict(sorted(best.items()))


def list_releases(client: httpx.Client, max_pages: int = 60) -> dict[str, EsmisRelease]:
    """Walk every API page (from page 0) and return the canonical release per report month."""
    releases = _with_xml(fetch_items(client, get_settings().esmis_api_url, max_pages))
    months = latest_per_month(releases)
    log.info("esmis.releases", releases=len(releases), months=len(months))
    return months
