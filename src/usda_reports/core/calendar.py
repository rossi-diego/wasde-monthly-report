"""Release calendars per report in ``config/calendars/<report_id>.yaml``.

Two forms are supported:

* explicit dates (``releases: [YYYY-MM-DD, …]``), used by WASDE;
* a weekly rule (``rule: {weekday, start, holiday_shift_days}``) plus ``overrides``
  (scheduled date → actual date) and ``cancelled`` dates, used by weekly reports such as
  Export Sales. A U.S. federal holiday from Monday up to the scheduled weekday moves that
  week's release ``holiday_shift_days`` later.

Release times always come from config (ET), never from the source's metadata: ESMIS stamps
many files with a dummy 12:00Z.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from usda_reports.core.holidays import is_federal_holiday

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
    "weekly_release_for",
    "weekly_releases",
]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
# How far ahead a weekly rule is expanded (dates beyond this are generated on demand).
RULE_HORIZON_DAYS = 400


def calendar_path(calendars_dir: Path, report_id: str) -> Path:
    return calendars_dir / f"{report_id}.yaml"


def _shift(scheduled: date, raw: dict[str, Any]) -> date | None:
    """Actual release date for a rule-scheduled date (None = cancelled)."""
    overrides = {str(k): str(v) for k, v in (raw.get("overrides") or {}).items()}
    if scheduled.isoformat() in overrides:
        return date.fromisoformat(overrides[scheduled.isoformat()])
    if scheduled.isoformat() in {str(d) for d in raw.get("cancelled") or []}:
        return None
    rule = raw["rule"]
    shift = int(rule.get("holiday_shift_days", 1))
    week_start = scheduled - timedelta(days=scheduled.weekday())
    days = (scheduled - week_start).days + 1
    if shift and any(is_federal_holiday(week_start + timedelta(days=i)) for i in range(days)):
        return scheduled + timedelta(days=shift)
    return scheduled


def weekly_releases(raw: dict[str, Any], until: date | None = None) -> list[date]:
    """Expand a weekly rule into actual release dates from ``rule.start`` to ``until``."""
    rule = raw["rule"]
    wd = WEEKDAYS.index(str(rule.get("weekday", "thursday")).lower())
    start = date.fromisoformat(str(rule["start"]))
    start += timedelta(days=(wd - start.weekday()) % 7)
    end = until or (datetime.now(UTC).date() + timedelta(days=RULE_HORIZON_DAYS))
    out = []
    d = start
    while d <= end:
        actual = _shift(d, raw)
        if actual is not None:
            out.append(actual)
        d += timedelta(days=7)
    return sorted(set(out))


def weekly_release_for(raw: dict[str, Any], period_end: date) -> date | None:
    """Release date of the week ending ``period_end`` (rule: the same weekday one week later,
    then holiday shift / overrides). Used to date backfilled history."""
    lag = int(raw["rule"].get("lag_days", 7))
    return _shift(period_end + timedelta(days=lag), raw)


def load_calendar_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_calendar(path: Path, until: date | None = None) -> list[date]:
    raw = load_calendar_raw(path)
    if "rule" in raw:
        return weekly_releases(raw, until)
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


def parse_time_et(hhmm: str) -> time:
    hh, mm = (int(x) for x in hhmm.split(":"))
    return time(hh, mm)


def latest_due(dates: list[date], now_utc: datetime, at: time = RELEASE_TIME_ET) -> date | None:
    """Most recent scheduled release whose publication time (``at`` ET) has passed."""
    due = [d for d in dates if release_datetime_utc(d, at) <= now_utc]
    return due[-1] if due else None


def is_overdue(
    dates: list[date],
    now_utc: datetime,
    ingested_months: set[str],
    grace_days: int = 3,
    at: time = RELEASE_TIME_ET,
    key_format: str = "%Y-%m",
) -> date | None:
    """Return the scheduled date if its report is still missing ``grace_days`` after release.

    ``ingested_months`` holds release keys in ``key_format`` (``%Y-%m`` for WASDE,
    ``%Y-%m-%d`` for weekly reports).
    """
    d = latest_due(dates, now_utc, at)
    if d is None or d.strftime(key_format) in ingested_months:
        return None
    if now_utc - release_datetime_utc(d, at) > timedelta(days=grace_days):
        return d
    return None
