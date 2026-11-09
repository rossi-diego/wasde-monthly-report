from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from wasde.bronze import BronzeStore
from wasde.detect import DetectError, months_between, run_detect, watchdogs
from wasde.manifest import Manifest, ReportEntry
from wasde.net import make_client
from wasde.sources.calendar import load_calendar, save_calendar
from wasde.sources.esmis import EsmisRelease
from wasde.sources.usda_csv import csv_url

CSV = b'"WasdeNumber","ReportDate"\n"677","November 2026"\n'
DATES = [date(2026, 10, 9), date(2026, 11, 10), date(2026, 12, 10)]


def _entry(month: str, version: int = 1, sha: str = "old") -> ReportEntry:
    return ReportEntry(
        source="usda_csv",
        file=f"usda_csv/{month}.csv",
        url="u",
        sha256=sha,
        bytes=1,
        version=version,
        fetched_at="t",
    )


def _lister(releases: dict[str, EsmisRelease]):
    calls = []

    def lister(client, max_pages=60):
        calls.append(max_pages)
        return releases

    lister.calls = calls  # type: ignore[attr-defined]
    return lister


@respx.mock
def test_new_report_on_release_day(tmp_path):
    respx.get(csv_url("2026-11")).mock(return_value=httpx.Response(200, content=CSV))
    store = BronzeStore(tmp_path, Manifest(reports={"2026-10": _entry("2026-10")}))
    now = datetime(2026, 11, 10, 17, 5, tzinfo=UTC)  # 12:05 ET
    with make_client() as c:
        res = run_detect(c, store, DATES, now, lister=_lister({}))
    assert res.ingested == ["2026-11"] and res.problems == []
    assert "2026-11" in store.manifest.reports


@respx.mock
def test_before_noon_nothing_happens(tmp_path):
    store = BronzeStore(tmp_path, Manifest(reports={"2026-10": _entry("2026-10")}))
    now = datetime(2026, 11, 10, 16, 35, tzinfo=UTC)  # 11:35 ET (EST)
    with make_client() as c:
        res = run_detect(c, store, DATES, now, lister=_lister({}))
    assert not res.new_report and res.due_month == "2026-10" and res.problems == []


@respx.mock
def test_revised_edition_is_reingested(tmp_path):
    respx.get(csv_url("2026-10")).mock(return_value=httpx.Response(200, content=CSV))
    store = BronzeStore(tmp_path, Manifest(reports={"2026-10": _entry("2026-10", version=1)}))
    v2 = {"2026-10": EsmisRelease("1", date(2026, 10, 9), "https://x/wasde1026v2.xml")}
    with make_client() as c:
        res = run_detect(c, store, DATES, datetime(2026, 10, 20, tzinfo=UTC), lister=_lister(v2))
    assert res.ingested == ["2026-10"]
    assert store.manifest.reports["2026-10"].version == 2


@respx.mock
def test_force_month_reads_all_pages_and_fails_loudly(tmp_path):
    store = BronzeStore(tmp_path, Manifest())
    lister = _lister({})
    with make_client() as c, pytest.raises(DetectError):
        run_detect(c, store, DATES, datetime(2026, 10, 20, tzinfo=UTC), "2012-05", lister=lister)
    assert lister.calls == [60]


def test_watchdogs():
    now = datetime(2026, 11, 20, tzinfo=UTC)
    assert watchdogs(DATES, now, {"2026-10", "2026-11"}, "2026-11") == []
    overdue = watchdogs(DATES, now, {"2026-10"}, "2026-10")
    assert any("still missing" in p for p in overdue)
    assert any(
        "no future date" in p
        for p in watchdogs(DATES, datetime(2027, 1, 5, tzinfo=UTC), {"2026-12"}, "2026-12")
    )
    assert any("stale" in p for p in watchdogs(DATES, now, {"2026-09"}, "2026-09"))
    assert months_between("2025-12", "2026-02") == 2


def test_save_calendar_replaces_scraped_years(tmp_path):
    path = tmp_path / "cal.yaml"
    save_calendar(path, [date(2025, 10, 9), date(2025, 11, 14), date(2026, 1, 12)])
    save_calendar(path, [date(2025, 11, 14)])  # 2025 re-scraped: Oct cancelled
    assert load_calendar(path) == [date(2025, 11, 14), date(2026, 1, 12)]
