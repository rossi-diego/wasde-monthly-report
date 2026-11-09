"""ESMIS public API (Cornell/NAL): ``/api/v1/release/findByIdentifier/<identifier>?page=N``.

Rules learned the hard way (plan §3 'ESMIS handling rules'):

* Paging is **0-based**: ``page=0`` is the newest page. Starting at 1 silently drops the newest
  25 releases.
* Results are not strictly sorted (e.g. FatsOils lists 2018-11-01 after 2018-12-03).
* File URLs must come from ``files[]``; file names are not predictable (``cafo0726.zip`` is the
  file name of both the 2026-07-01 and the 2026-08-03 Fats & Oils releases).
* ``release_datetime`` carries the right **date** but a dummy time (``12:00:00+0000``); the
  release time always comes from ``config/reports.yaml``.
* Some releases carry no data file at all (e.g. a reschedule notice).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from usda_reports.core.logs import get_logger
from usda_reports.core.net import get

log = get_logger(__name__)

DEFAULT_MAX_PAGES = 60


@dataclass(frozen=True)
class EsmisItem:
    """One ESMIS release as listed by ``findByIdentifier``."""

    release_id: str
    release_date: date  # date part of release_datetime (the time part is a placeholder)
    files: tuple[str, ...]
    title: str = ""

    def file_with_suffix(self, *suffixes: str) -> str | None:
        """First file URL whose name ends with one of ``suffixes`` (case-insensitive)."""
        low = tuple(s.lower() for s in suffixes)
        return next((f for f in self.files if f.lower().endswith(low)), None)

    @property
    def release_key(self) -> str:
        """Release key of a dated report (``YYYY-MM-DD``, from ``release_datetime``)."""
        return self.release_date.isoformat()


def parse_items(payload: dict[str, Any]) -> list[EsmisItem]:
    """Every result of one API page that has a usable ``release_datetime``."""
    out: list[EsmisItem] = []
    for item in payload.get("results") or []:
        raw_dt = str(item.get("release_datetime") or "")
        if len(raw_dt) < 10:
            continue
        try:
            day = date.fromisoformat(raw_dt[:10])
        except ValueError:
            continue
        out.append(
            EsmisItem(
                release_id=str(item.get("id")),
                release_date=day,
                files=tuple(str(f) for f in item.get("files") or []),
                title=str(item.get("title") or ""),
            )
        )
    return out


def page_url(base_url: str, page: int) -> str:
    return f"{base_url}?page={page}"


def fetch_items(
    client: httpx.Client, base_url: str, max_pages: int = DEFAULT_MAX_PAGES
) -> list[EsmisItem]:
    """Walk pages 0..N of one identifier (``max_pages=1`` = only the newest page).

    ``base_url`` is the full ``.../findByIdentifier/<identifier>`` URL. Items are returned in
    API order (not sorted)."""
    items: list[EsmisItem] = []
    for page in range(max_pages):
        resp = get(client, page_url(base_url, page))
        if resp is None:
            break
        payload = resp.json()
        items.extend(parse_items(payload))
        total_pages = int((payload.get("pager") or {}).get("total_pages") or 0)
        if page + 1 >= total_pages or not payload.get("results"):
            break
    log.info("esmis.items", url=base_url, items=len(items))
    return items
