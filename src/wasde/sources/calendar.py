"""Official WASDE release calendar.

USDA publishes the dates as prose on the WASDE page ("In 2026 the WASDE report will be
released on Jan. 12, Feb. 10, ..."). We parse that into ``config/release_calendar.yaml``
so detection runs only on real release days; skipped months (shutdowns) are simply absent.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

EASTERN = ZoneInfo("America/New_York")
RELEASE_TIME_ET = time(12, 0)

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}
_DATE_TOKEN = r"[A-Z][a-z]{2,8}\.?\s+\d{1,2}"
_YEAR_BLOCK = re.compile(
    r"In\s+(20\d{2})\s+the\s+WASDE\s+report\s+will\s+be\s+released\s+on\s+"
    rf"((?:{_DATE_TOKEN}\s*,?\s*(?:and\s+)?)+)",
    re.IGNORECASE,
)
_DAY = re.compile(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})")


def parse_calendar_html(html: str) -> list[date]:
    """Extract every announced release date from the USDA WASDE page."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", unescape(text).replace("\xa0", " "))
    dates: set[date] = set()
    for year_s, body in _YEAR_BLOCK.findall(text):
        for mon_s, day_s in _DAY.findall(body):
            mon = _MONTHS.get(mon_s.lower())
            if mon:
                dates.add(date(int(year_s), mon, int(day_s)))
    return sorted(dates)


def load_calendar(path: Path) -> list[date]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return sorted(date.fromisoformat(str(d)) for d in raw.get("releases", []))


def save_calendar(path: Path, dates: list[date]) -> None:
    merged = sorted(set(load_calendar(path)) | set(dates))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "source": "https://www.usda.gov/.../commodity-markets/wasde-report",
        "release_time_et": "12:00",
        "releases": [d.isoformat() for d in merged],
    }
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def release_datetime_utc(d: date) -> datetime:
    return datetime.combine(d, RELEASE_TIME_ET, EASTERN).astimezone(ZoneInfo("UTC"))


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
