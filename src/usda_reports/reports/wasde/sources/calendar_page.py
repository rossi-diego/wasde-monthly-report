"""Scrape the official WASDE release dates from usda.gov.

USDA publishes the dates as prose on the WASDE page ("In 2026 the WASDE report will be
released on Jan. 12, Feb. 10, ..."). We parse that into ``config/calendars/wasde.yaml``
so detection runs only on real release days; skipped months (shutdowns) are simply absent.
"""

from __future__ import annotations

import re
from datetime import date
from html import unescape

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
