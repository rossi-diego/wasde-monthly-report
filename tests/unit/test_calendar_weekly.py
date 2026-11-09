"""Weekly release calendar (Export Sales): Thursday rule, federal-holiday shift, overrides,
and the detect ET-clock guard / watchdogs."""

from __future__ import annotations

from datetime import UTC, date, datetime

from usda_reports.core.calendar import (
    load_calendar,
    load_calendar_raw,
    weekly_release_for,
    weekly_releases,
)
from usda_reports.core.holidays import federal_holidays, is_federal_holiday
from usda_reports.detect import weekly_due

RULE = {"rule": {"weekday": "thursday", "start": "2026-10-01", "lag_days": 7}}


def test_federal_holidays_known_dates():
    h = federal_holidays(2026)
    assert date(2026, 11, 26) in h  # Thanksgiving (4th Thursday)
    assert date(2026, 11, 11) in h  # Veterans Day (Wednesday)
    assert date(2026, 7, 3) in h  # July 4 is a Saturday → observed Friday
    assert date(2026, 6, 19) in h  # Juneteenth (since 2021)
    assert date(2020, 6, 19) not in federal_holidays(2020)
    assert is_federal_holiday(date(2026, 9, 7))  # Labor Day
    assert not is_federal_holiday(date(2026, 11, 12))


def test_weekly_rule_shifts_for_holidays_in_the_release_week():
    dates = weekly_releases(RULE, until=date(2026, 12, 31))
    assert date(2026, 11, 5) in dates  # ordinary Thursday
    assert date(2026, 11, 13) in dates and date(2026, 11, 12) not in dates  # Veterans Day (Wed)
    assert date(2026, 11, 27) in dates and date(2026, 11, 26) not in dates  # Thanksgiving
    assert date(2026, 12, 25) not in dates  # Christmas is a Friday: Thursday 24 unaffected
    assert date(2026, 12, 24) in dates
    assert all(d.weekday() in (3, 4) for d in dates)


def test_week_ending_maps_to_its_release():
    assert weekly_release_for(RULE, date(2026, 10, 29)) == date(2026, 11, 5)
    assert weekly_release_for(RULE, date(2026, 11, 5)) == date(2026, 11, 13)
    raw = {**RULE, "overrides": {"2026-11-19": "2026-11-23"}, "cancelled": ["2026-12-03"]}
    assert weekly_release_for(raw, date(2026, 11, 12)) == date(2026, 11, 23)
    assert weekly_release_for(raw, date(2026, 11, 26)) is None
    assert date(2026, 12, 3) not in weekly_releases(raw, until=date(2026, 12, 31))


def test_repo_calendar_is_a_weekly_rule(config_dir):
    path = config_dir / "calendars" / "export_sales.yaml"
    raw = load_calendar_raw(path)
    assert raw["release_time_et"] == "08:30" and raw["rule"]["weekday"] == "thursday"
    dates = load_calendar(path, until=date(2026, 11, 30))
    assert dates[0] == date(2010, 6, 10)
    assert date(2026, 11, 5) in dates


DATES = weekly_releases(RULE, until=date(2027, 3, 1))


def test_nothing_due_before_the_et_release_time():
    # Thursday 2026-11-05 13:29 UTC = 08:29 EST: the new release is not due yet.
    st = weekly_due(DATES, datetime(2026, 11, 5, 13, 29, tzinfo=UTC), {"2026-10-29"}, "08:30")
    assert st.due == date(2026, 10, 29) and not st.missing and not st.problems


def test_due_and_missing_after_release_time():
    st = weekly_due(DATES, datetime(2026, 11, 5, 13, 31, tzinfo=UTC), {"2026-10-29"}, "08:30")
    assert st.due == date(2026, 11, 5) and st.missing and not st.problems


def test_api_date_a_day_off_the_rule_counts_as_ingested():
    st = weekly_due(DATES, datetime(2026, 11, 13, 15, 0, tzinfo=UTC), {"2026-11-12"}, "08:30")
    assert not st.missing


def test_watchdogs_overdue_and_stale():
    st = weekly_due(DATES, datetime(2026, 11, 9, 12, 0, tzinfo=UTC), {"2026-10-22"}, "08:30")
    assert st.missing
    assert any("still missing" in p for p in st.problems)
    stale = weekly_due(DATES, datetime(2026, 11, 20, 12, 0, tzinfo=UTC), {"2026-10-22"}, "08:30")
    assert any("going stale" in p for p in stale.problems)
    empty = weekly_due([date(2026, 1, 1)], datetime(2026, 11, 9, tzinfo=UTC), set(), "08:30")
    assert any("no future date" in p for p in empty.problems)


def test_shutdown_catch_up_weeks_are_pinned_to_their_real_release(config_dir):
    """Catch-up releases after a funding lapse come out later than the Thursday rule; the
    overrides pin them (FAS catch-up schedule) so ASOF joins see the WASDE public then."""
    from usda_reports.reports.export_sales.parse import release_ts_source_for

    raw = load_calendar_raw(config_dir / "calendars" / "export_sales.yaml")
    # Week ending 2025-10-30: the rule says 2025-11-06, FAS released it on 2025-12-04
    # (after the 2025-11 WASDE of 2025-11-14).
    assert weekly_release_for(raw, date(2025, 10, 30)) == date(2025, 12, 4)
    assert release_ts_source_for(raw, date(2025, 10, 30)) == "calendar_override"
    assert weekly_release_for(raw, date(2025, 9, 25)) == date(2025, 11, 13)
    assert weekly_release_for(raw, date(2018, 12, 20)) == date(2019, 1, 31)
    assert weekly_release_for(raw, date(2013, 9, 26)) == date(2013, 10, 18)
    # The last on-time week before the lapse and the first regular week after it.
    assert weekly_release_for(raw, date(2025, 9, 18)) == date(2025, 9, 25)
    assert release_ts_source_for(raw, date(2025, 9, 18)) == "calendar_rule"
    assert weekly_release_for(raw, date(2026, 1, 1)) == date(2026, 1, 8)
    # An override never moves a release earlier than its scheduled date.
    for scheduled, actual in raw["overrides"].items():
        assert date.fromisoformat(str(actual)) >= date.fromisoformat(str(scheduled))
