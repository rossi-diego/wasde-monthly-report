from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from wasde.bronze import BronzeStore, find_seed_files, ingest_month, looks_like_xml, month_range
from wasde.manifest import Manifest
from wasde.net import SourceBlockedError, make_client
from wasde.sources.calendar import (
    is_overdue,
    latest_due,
    parse_calendar_html,
    release_datetime_utc,
    scheduled_for_month,
)
from wasde.sources.esmis import EsmisRelease, latest_per_month, parse_releases
from wasde.sources.usda_csv import NotACsvError, csv_url, fetch_csv

CAL_HTML = """
<h5><strong>2026 WASDE Release Dates (12:00pm ET)</strong></h5>
<p><strong>In 2026 the WASDE report will be released on Jan. 12, Feb. 10, Mar. 10, Apr.&nbsp;9, May 12,
Jun. 11, Jul. 10, Aug. 12, Sep. 11, Oct. 9, Nov. 10, and Dec. 10.</strong></p>
<h5>2027 WASDE Release Dates</h5><p>In 2027 the WASDE report will be released on Jan. 12, and Feb. 10.</p>
<h3>November 2026 WASDE Report</h3>
"""


def test_parse_calendar():
    dates = parse_calendar_html(CAL_HTML)
    assert len(dates) == 14
    assert dates[0] == date(2026, 1, 12) and dates[-1] == date(2027, 2, 10)
    assert date(2026, 4, 9) in dates


def test_release_time_handles_dst():
    assert release_datetime_utc(date(2026, 7, 10)).hour == 16  # EDT
    assert release_datetime_utc(date(2026, 12, 10)).hour == 17  # EST


def test_latest_due_and_overdue():
    dates = parse_calendar_html(CAL_HTML)
    before = datetime(2026, 11, 10, 16, 59, tzinfo=UTC)
    after = datetime(2026, 11, 10, 17, 1, tzinfo=UTC)
    assert latest_due(dates, before) == date(2026, 10, 9)
    assert latest_due(dates, after) == date(2026, 11, 10)
    assert (
        is_overdue(dates, datetime(2026, 11, 12, tzinfo=UTC), {"2026-10"}) is None
    )  # within grace
    assert is_overdue(dates, datetime(2026, 11, 14, tzinfo=UTC), {"2026-10"}) == date(2026, 11, 10)
    assert is_overdue(dates, datetime(2026, 11, 14, tzinfo=UTC), {"2026-11"}) is None
    assert scheduled_for_month(dates, "2026-05") == date(2026, 5, 12)


def test_esmis_parse_and_latest_per_month():
    payload = {
        "results": [
            {
                "id": "1",
                "release_datetime": "2026-05-12T12:00:00+0000",
                "files": ["https://x/wasde0526.xml", "https://x/a.pdf"],
            },
            {
                "id": "2",
                "release_datetime": "2026-05-12T12:00:00+0000",
                "files": ["https://x/wasde0526v2.xml"],
            },
            {
                "id": "3",
                "release_datetime": "2010-01-12T12:00:00+0000",
                "files": ["https://x/wasde0110.pdf"],
            },
        ]
    }
    rel = parse_releases(payload)
    assert [r.release_id for r in rel] == ["1", "2"]  # PDF-only release skipped
    best = latest_per_month(rel)
    assert best["2026-05"].version == 2


def test_month_range():
    assert month_range("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_find_seed_files(tmp_path):
    for name in [
        "2013-08-12_ORIGwasde-08-12-2013.xml",
        "2013-08-12_wasde-08-12-2013.xml",
        "2025-04-10_wasde0425.xml",
        "2025-04-10_wasde0425v2.xml",
        "2018-12-11_latest.xml",
        "2018-12-14_latest.xml",
        "notes.txt",
    ]:
        (tmp_path / name).write_text("<x/>")
    seeds = find_seed_files(tmp_path)
    assert seeds["2013-08"].name == "2013-08-12_wasde-08-12-2013.xml"
    assert seeds["2025-04"].name == "2025-04-10_wasde0425v2.xml"
    assert seeds["2018-12"].name == "2018-12-14_latest.xml"


@pytest.mark.parametrize(
    ("data", "ok"),
    [
        (b'\xef\xbb\xbf<?xml version="1.0"?><Report/>', True),
        (b"<Report/>", True),
        (b"<!DOCTYPE html><html>", False),
        (b"<html><body>Denied", False),
    ],
)
def test_looks_like_xml(data, ok):
    assert looks_like_xml(data) is ok


@respx.mock
def test_fetch_csv_accepts_quoted_header_and_rejects_html():
    url = csv_url("2024-05")
    respx.get(url).mock(return_value=httpx.Response(200, content=b'"WasdeNumber","ReportDate"\n'))
    with make_client() as c:
        assert fetch_csv(c, "2024-05").startswith(b'"WasdeNumber"')
    respx.get(url).mock(return_value=httpx.Response(200, content=b"<html>maintenance</html>"))
    with make_client() as c, pytest.raises(NotACsvError):
        fetch_csv(c, "2024-05")


@respx.mock
def test_blocked_source_raises():
    respx.get(csv_url("2024-05")).mock(return_value=httpx.Response(403, content=b"Access Denied"))
    with make_client() as c, pytest.raises(SourceBlockedError):
        fetch_csv(c, "2024-05")


@respx.mock
def test_ingest_falls_back_to_esmis_xml_when_csv_missing(tmp_path):
    respx.get(csv_url("2026-05")).mock(return_value=httpx.Response(404))
    xml_url = "https://esmis.example/wasde0526v2.xml"
    respx.get(xml_url).mock(
        return_value=httpx.Response(200, content=b'\xef\xbb\xbf<?xml version="1.0"?><Report/>')
    )
    store = BronzeStore(tmp_path, Manifest())
    esmis = {"2026-05": EsmisRelease("795903", date(2026, 5, 12), xml_url)}
    with make_client() as c:
        entry = ingest_month(c, store, "2026-05", esmis)
    assert entry is not None and entry.source == "esmis_xml" and entry.version == 2
    assert (tmp_path / "esmis_xml" / "2026-05.xml").exists()
    assert store.verify() == []
    (tmp_path / "esmis_xml" / "2026-05.xml").write_bytes(b"tampered")
    assert store.verify() == ["2026-05"]


def test_manifest_roundtrip(tmp_path):
    m = Manifest(latest_report="2026-10")
    m.save(tmp_path / "manifest.json")
    assert Manifest.load(tmp_path / "manifest.json").latest_report == "2026-10"
    assert Manifest.load(tmp_path / "missing.json").reports == {}
