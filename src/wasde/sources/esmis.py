"""ESMIS public API (Cornell/NAL): the only discoverable index of historical WASDE files.

File URLs before 2025 are not predictable, so they must come from the API.
Caveats handled here: results are not strictly sorted, ``release_datetime`` is labelled
UTC but is really 12:00 ET, a month can have several releases (revised ``v2`` editions,
odd one-offs), and some releases have no XML (pre 2010-07: PDF/TXT only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import httpx

from wasde.config import get_settings
from wasde.logs import get_logger
from wasde.net import get

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


def parse_releases(payload: dict) -> list[EsmisRelease]:
    """Parse one API page into releases that carry an XML file."""
    out: list[EsmisRelease] = []
    for item in payload.get("results", []):
        xml = [f for f in item.get("files", []) if f.lower().endswith(".xml")]
        raw_dt = item.get("release_datetime") or ""
        if not xml or len(raw_dt) < 10:
            continue
        out.append(
            EsmisRelease(
                release_id=str(item.get("id")),
                release_date=date.fromisoformat(raw_dt[:10]),
                xml_url=xml[0],
            )
        )
    return out


def latest_per_month(releases: list[EsmisRelease]) -> dict[str, EsmisRelease]:
    """Keep one release per report month: highest version, then latest date."""
    best: dict[str, EsmisRelease] = {}
    for r in releases:
        cur = best.get(r.report_month)
        if cur is None or (r.version, r.release_date) > (cur.version, cur.release_date):
            best[r.report_month] = r
    return dict(sorted(best.items()))


def list_releases(client: httpx.Client, max_pages: int = 60) -> dict[str, EsmisRelease]:
    """Walk every API page and return the canonical release per report month."""
    url = get_settings().esmis_api_url
    releases: list[EsmisRelease] = []
    for page in range(max_pages):
        resp = get(client, f"{url}?page={page}")
        if resp is None:
            break
        payload = resp.json()
        batch = parse_releases(payload)
        releases.extend(batch)
        total_pages = payload.get("pager", {}).get("total_pages", 0)
        if page + 1 >= total_pages or not payload.get("results"):
            break
    months = latest_per_month(releases)
    log.info("esmis.releases", releases=len(releases), months=len(months))
    return months
