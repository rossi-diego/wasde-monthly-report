"""Release-day detection: decide whether there is anything new to ingest, and raise the alarm
when the data is going stale.

Watchdogs exist because the previous version of this project failed silently for 18 months:
a run must never be green when the calendar has run out, a scheduled report is overdue, or
the newest report in the manifest is too old.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from usda_reports.bronze.store import BronzeStore
from usda_reports.core.calendar import (
    is_overdue,
    latest_due,
    load_calendar,
    parse_time_et,
    release_datetime_utc,
)
from usda_reports.core.logs import get_logger
from usda_reports.reports.wasde.ingest import ingest_month
from usda_reports.reports.wasde.sources.esmis import EsmisRelease, list_releases

if TYPE_CHECKING:
    from usda_reports.core.registry import ReportConfig

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
        problems.append("release calendar has no future date: run `usda-reports refresh-calendar`")
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
    releases = store.entries
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
    for month in sorted(releases)[-2:]:
        entry = releases[month]
        rel = recent.get(month)
        if rel and rel.version > entry.edition:
            old_sha = entry.sha256
            fresh = ingest_month(client, store, month, recent, version=rel.version)
            if fresh and fresh.sha256 != old_sha:
                log.info("detect.revised_edition", month=month, version=rel.version)
                result.ingested.append(month)

    due = latest_due(dates, now)
    if due:
        result.due_month = f"{due:%Y-%m}"
        if result.due_month not in releases:
            entry = ingest_month(client, store, result.due_month, recent)
            if entry:
                log.info("detect.ingested", month=result.due_month, source=entry.source)
                result.ingested.append(result.due_month)
            else:
                log.info("detect.not_yet_available", month=result.due_month)

    latest = max(releases) if releases else None
    result.problems = watchdogs(dates, now, set(releases), latest)
    return result


# ── date-keyed reports (Export Sales weekly, oilseed crush monthly) ──────────


@dataclass
class WeeklyDue:
    """Calendar state of a date-keyed report at ``now`` (no network needed)."""

    due: date | None  # latest scheduled release whose ET publication time has passed
    have_latest: str | None  # newest ingested release key (YYYY-MM-DD)
    missing: bool  # the due release is not in bronze yet
    problems: list[str] = field(default_factory=list)


def weekly_due(
    dates: list[date],
    now: datetime,
    have: set[str],
    release_time_et: str,
    grace_days: int = 10,
    overdue_days: int = 2,
    cadence_days: int = 7,
) -> WeeklyDue:
    """Is a release of a date-keyed report due and missing? Plus the watchdogs (calendar,
    overdue, stale). Used by weekly reports and by monthly NASS reports (``cadence_days=31``).

    A release counts as ingested when bronze holds a key within 3 days before the scheduled
    date or any time after it: the source's own release date can differ from the calendar by
    a day (holiday shifts the rule did not model), and a newer key implies the older one too.
    """
    at = parse_time_et(release_time_et)
    due = latest_due(dates, now, at)
    latest = max(have) if have else None
    missing = False
    problems: list[str] = []
    if not any(d > now.date() for d in dates):
        problems.append("release calendar has no future date")
    if due is not None:
        floor = (due - timedelta(days=3)).isoformat()
        missing = latest is None or latest < floor
        if missing and now - release_datetime_utc(due, at) > timedelta(days=overdue_days):
            problems.append(f"release scheduled for {due} is still missing")
    # Staleness is measured up to the newest scheduled release plus one cadence, never beyond:
    # a seasonal report (Crop Progress, April-November) has nothing due from December to
    # March, so its final November release must not count as stale all winter. For reports
    # released all year the reference is simply today (the calendar always has a date within
    # one cadence; an exhausted calendar is its own problem above).
    ref = now.date() if due is None else min(now.date(), due + timedelta(days=cadence_days))
    if latest and (ref - date.fromisoformat(latest)).days > cadence_days + grace_days:
        problems.append(f"newest release is {latest}: data is going stale")
    return WeeklyDue(due=due, have_latest=latest, missing=missing, problems=problems)


def missed_since(
    calendar_path: Path, latest_key: str, now: datetime, cfg: ReportConfig
) -> list[date]:
    """Scheduled releases of a date-keyed report whose publication instant has passed since
    ``latest_key`` (3-day tolerance, as in :func:`weekly_due`). Empty for a seasonal report
    between its final release and the next season: nothing was due, so nothing is stale."""
    at = parse_time_et(cfg.release_time_et)
    floor = date.fromisoformat(latest_key) + timedelta(days=3)
    return [
        d
        for d in load_calendar(calendar_path, until=now.date())
        if d > floor and release_datetime_utc(d, at) <= now
    ]
