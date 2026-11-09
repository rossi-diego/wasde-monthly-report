"""U.S. federal holidays (5 U.S.C. 6103), used to shift weekly release dates.

FAS publishes Export Sales on Thursday at 08:30 ET; when a federal holiday falls in the
release week (Monday to Thursday) the report moves one day later. Observed dates follow the
federal rule: a Saturday holiday is observed on Friday, a Sunday holiday on Monday.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th ``weekday`` (Mon=0) of a month; n=-1 = last."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def federal_holidays(year: int) -> frozenset[date]:
    """Observed U.S. federal holidays of ``year``."""
    fixed = [date(year, 1, 1), date(year, 7, 4), date(year, 11, 11), date(year, 12, 25)]
    if year >= 2021:
        fixed.append(date(year, 6, 19))  # Juneteenth (since 2021)
    floating = [
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _nth_weekday(year, 5, 0, -1),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 10, 0, 2),  # Columbus Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
    ]
    days = {_observed(d) for d in fixed} | set(floating)
    # New Year's Day of the next year observed on Dec 31 of this one.
    nxt = date(year + 1, 1, 1)
    if nxt.weekday() == 5:
        days.add(date(year, 12, 31))
    return frozenset(days)


def is_federal_holiday(d: date) -> bool:
    return d in federal_holidays(d.year)
