"""Release-day detection: decide whether there is anything new to ingest, and raise the alarm
when the data is going stale.

Watchdogs exist because the previous version of this project failed silently for 18 months:
a run must never be green when the calendar has run out, a scheduled report is overdue, or
the newest report in the manifest is too old.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx

from wasde.bronze import BronzeStore, ingest_month
from wasde.logs import get_logger
from wasde.sources.calendar import is_overdue, latest_due
from wasde.sources.esmis import EsmisRelease, list_releases

log = get_logger(__name__)

Lister = Callable[..., dict[str, EsmisRelease]]


class DetectError(RuntimeError):
    pass


@dataclass
class DetectResult:
    ingested: list[str] = field(default_factory=list)  # months new or changed in bronze
    due_month: str | None = None
    problems: list[str] = field(default_factory=list)  # watchdog alarms

    @property
    def new_report(self) -> bool:
        return bool(self.ingested)


def months_between(a: str, b: str) -> int:
    ya, ma = (int(x) for x in a.split("-"))
    yb, mb = (int(x) for x in b.split("-"))
    return (yb - ya) * 12 + (mb - ma)


def watchdogs(dates: list[date], now: datetime, have: set[str], latest: str | None) -> list[str]:
    problems = []
    if not any(d > now.date() for d in dates):
        problems.append("release calendar has no future date: run `wasde refresh-calendar`")
    overdue = is_overdue(dates, now, have)
    if overdue:
        problems.append(f"report scheduled for {overdue} is still missing")
    if latest and months_between(latest, f"{now:%Y-%m}") >= 2:
        problems.append(f"newest report is {latest}: data is going stale")
    return problems


def run_detect(
    client: httpx.Client,
    store: BronzeStore,
    dates: list[date],
    now: datetime,
    force_month: str | None = None,
    lister: Lister = list_releases,
) -> DetectResult:
    manifest = store.manifest
    result = DetectResult()

    if force_month:
        esmis = lister(client)  # every page: the month may be years old
        entry = ingest_month(client, store, force_month, esmis)
        if entry is None:
            raise DetectError(f"{force_month}: no CSV or ESMIS XML found")
        result.ingested.append(force_month)
        return result

    recent = lister(client, max_pages=1)

    # Revised editions ("v2") of recent reports: re-ingest when ESMIS shows a newer version.
    for month in sorted(manifest.reports)[-2:]:
        entry = manifest.reports[month]
        rel = recent.get(month)
        if rel and rel.version > entry.version:
            old_sha = entry.sha256
            fresh = ingest_month(client, store, month, recent, version=rel.version)
            if fresh and fresh.sha256 != old_sha:
                log.info("detect.revised_edition", month=month, version=rel.version)
                result.ingested.append(month)

    due = latest_due(dates, now)
    if due:
        result.due_month = f"{due:%Y-%m}"
        if result.due_month not in manifest.reports:
            entry = ingest_month(client, store, result.due_month, recent)
            if entry:
                log.info("detect.ingested", month=result.due_month, source=entry.source)
                result.ingested.append(result.due_month)
            else:
                log.info("detect.not_yet_available", month=result.due_month)

    latest = max(manifest.reports) if manifest.reports else None
    result.problems = watchdogs(dates, now, set(manifest.reports), latest)
    return result
