"""Release calendars: explicit dates per report in ``config/calendars/<report_id>.yaml``.

Release times always come from config (ET), never from the source's metadata: ESMIS stamps
many files with a dummy 12:00Z.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

CALENDAR_SOURCE = "https://www.usda.gov/.../commodity-markets/wasde-report"

EASTERN = ZoneInfo("America/New_York")
RELEASE_TIME_ET = time(12, 0)

__all__ = [
    "EASTERN",
    "RELEASE_TIME_ET",
    "is_overdue",
    "latest_due",
    "load_calendar",
    "release_datetime_utc",
    "save_calendar",
    "scheduled_for_month",
]


def calendar_path(calendars_dir: Path, report_id: str) -> Path:
    return calendars_dir / f"{report_id}.yaml"


def load_calendar(path: Path) -> list[date]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return sorted(date.fromisoformat(str(d)) for d in raw.get("releases", []))


def save_calendar(
    path: Path, dates: list[date], source: str = CALENDAR_SOURCE, release_time_et: str = "12:00"
) -> None:
    """Merge scraped dates: a year present in the scrape replaces that year entirely (so
    cancelled or moved releases disappear); other years are kept."""
    scraped_years = {d.year for d in dates}
    kept = {d for d in load_calendar(path) if d.year not in scraped_years}
    merged = sorted(kept | set(dates))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "source": source,
        "release_time_et": release_time_et,
        "releases": [d.isoformat() for d in merged],
    }
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def release_datetime_utc(d: date, at: time = RELEASE_TIME_ET) -> datetime:
    return datetime.combine(d, at, EASTERN).astimezone(ZoneInfo("UTC"))


def scheduled_for_month(dates: list[date], report_month: str) -> date | None:
    for d in dates:
        if f"{d:%Y-%m}" == report_month:
            return d
    return None


def latest_due(dates: list[date], now_utc: datetime) -> date | None:
    """Most recent scheduled release whose 12:00 ET publication time has passed."""
    due = [d for d in dates if release_datetime_utc(d) <= now_utc]
    return due[-1] if due else None


def is_overdue(
    dates: list[date], now_utc: datetime, ingested_months: set[str], grace_days: int = 3
) -> date | None:
    """Return the scheduled date if its report is still missing ``grace_days`` after release."""
    d = latest_due(dates, now_utc)
    if d is None or f"{d:%Y-%m}" in ingested_months:
        return None
    if now_utc - release_datetime_utc(d) > timedelta(days=grace_days):
        return d
    return None
