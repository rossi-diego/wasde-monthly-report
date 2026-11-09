"""NASS Crop Progress: parser, calendar (Monday rule, April-November, holiday Tuesday), ingest,
season state (in season / closed, frozen clocks), insights C1–C3, the staleness exemption and
the home-card rules. Fixtures are real ESMIS zips (trimmed to prog_all_tables.csv) and slices
of the gold marts recorded from the 2026-11-09 local run (no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import httpx
import pytest
import respx

from usda_reports.bronze.store import BronzeStore
from usda_reports.core.calendar import load_calendar
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.manifest import Manifest
from usda_reports.core.registry import load_registry
from usda_reports.core.vocab import UnseenLabelError
from usda_reports.detect import weekly_due
from usda_reports.insights import gates as gates_mod
from usda_reports.insights.hero import crop_progress_card, home_cards
from usda_reports.insights.rules import crop_progress as cp
from usda_reports.insights.schema import Gates, InputRef, Insight
from usda_reports.nass_common.csv_tables import parse_value
from usda_reports.nass_common.ingest import ingest_zips
from usda_reports.nass_common.spec import StoredRelease
from usda_reports.reports.crop_progress.parse import (
    build_frame,
    classify,
    parse_date,
    parse_release,
    validate,
)
from usda_reports.reports.crop_progress.source import CropProgressError, SourceConfig

FX = Path(__file__).resolve().parents[1] / "fixtures" / "crop_progress"
URL = "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/CropProg"
IN_SEASON = datetime(2026, 11, 9, 22, 0, tzinfo=UTC)  # after Monday 16:00 ET, Nov 9 not ingested
OFF_SEASON = datetime(2026, 12, 15, 15, 0, tzinfo=UTC)


@pytest.fixture
def cfg(config_dir: Path) -> SourceConfig:
    return SourceConfig.load(config_dir / "reports" / "crop_progress" / "source.yaml")


@pytest.fixture
def calendar(config_dir: Path) -> list[date]:
    return load_calendar(config_dir / "calendars" / "crop_progress.yaml", until=date(2027, 12, 31))


def zip_bytes(key: str) -> bytes:
    return (FX / f"{key}.zip").read_bytes()


def rel(key: str) -> StoredRelease:
    return StoredRelease(key=key, sha256="0" * 64, edition=1, url=None, data=zip_bytes(key))


# ------------------------------------------------------------------ parser


def test_titles_are_classified_and_unknown_stages_fail(cfg):
    tk = classify("Corn Harvested – Selected States", cfg)
    assert tk is not None and (tk.crop, tk.kind, tk.category) == ("corn", "progress", "harvested")
    tk = classify("Soybean Condition – Selected States: Week Ending October 11, 2026", cfg)
    assert tk is not None and (tk.crop, tk.kind) == ("soybeans", "condition")
    assert tk.week_ending == date(2026, 10, 11)
    assert classify("Cotton Harvested – Selected States", cfg) is None
    with pytest.raises(UnseenLabelError):
        classify("Corn Tasseled – Selected States", cfg)
    assert parse_date("Sept. 7, 2014") == date(2014, 9, 7)


def test_release_2026_11_02_matches_the_published_text(cfg):
    df = parse_release(zip_bytes("2026-11-02"), cfg)
    assert set(df.week_ending) == {date(2026, 11, 1)}
    corn = df[(df.crop == "corn") & (df.category == "harvested")].iloc[0]
    # prog4426.txt: "18 States ......:  (NA)  60  74  77"
    assert (corn.value, corn.nass_prev_week_pct, corn.nass_5yr_avg_pct) == (74, 60, 77)
    assert corn.nass_prev_year_pct is None or corn.nass_prev_year_pct != corn.nass_prev_year_pct
    assert corn.avg_years == "2021-2025" and corn.n_states == 18
    ww = df[(df.crop == "winter_wheat") & (df.kind == "condition")].set_index("category").value
    assert ww.to_dict() == {
        "very_poor": 5, "poor": 13, "fair": 38, "good": 38, "excellent": 6
    }  # fmt: skip
    assert (df.commodity_id[df.crop == "winter_wheat"] == "wheat").all()


def test_mid_season_release_has_every_crop_and_condition(cfg):
    df = parse_release(zip_bytes("2026-07-06"), cfg)
    cond = df[df.kind == "condition"]
    assert set(cond.crop) == {"corn", "soybeans", "winter_wheat", "spring_wheat"}
    assert (cond.groupby("crop").value.sum().sub(100).abs() <= 1).all()
    assert set(df[df.crop == "spring_wheat"].n_states) == {6}


def test_old_layout_revised_marks_and_bare_na(cfg):
    df = parse_release(zip_bytes("2010-06-07"), cfg)
    assert set(df.week_ending) == {date(2010, 6, 6)} and len(df) > 10
    assert parse_value("* 61") == (61.0, "revised")
    assert parse_value("NA") == (None, "NA")
    parse_release(zip_bytes("2012-08-27"), cfg)  # "* 16" revised previous-week cells
    parse_release(zip_bytes("2018-08-06"), cfg)  # bare "NA" cells


def test_build_frame_envelope_lag_and_contract(cfg, config_dir):
    silver = build_frame([rel("2026-10-26"), rel("2026-11-02")], cfg)
    assert list(silver.release_key.unique()) == ["2026-10-26", "2026-11-02"]
    ts = silver[silver.release_key == "2026-11-02"].release_ts_utc.iloc[0]
    assert ts.isoformat() == "2026-11-02T21:00:00+00:00"  # 16:00 ET (EST)
    assert set(silver.vintage_quality) == {"as_published"}
    validate(silver, Contract.load(config_dir / "contracts" / "crop_progress.yaml"))
    bad = silver.copy()
    bad.loc[(bad.kind == "condition") & (bad.category == "good"), "value"] += 5
    with pytest.raises(ContractError):
        validate(bad, Contract.load(config_dir / "contracts" / "crop_progress.yaml"))
    with pytest.raises(CropProgressError):  # zip of 2026-11-02 stored under a wrong key
        build_frame([StoredRelease("2026-11-20", "0" * 64, 1, None, zip_bytes("2026-11-02"))], cfg)


# ------------------------------------------------------------------ calendar, detect


def test_calendar_mondays_april_to_november_with_holiday_tuesdays(calendar):
    y26 = [d for d in calendar if d.year == 2026]
    assert y26[0] == date(2026, 4, 6) and y26[-1] == date(2026, 11, 30)
    assert all(d.month in range(4, 12) for d in calendar)
    assert date(2026, 5, 26) in y26 and date(2026, 5, 25) not in y26  # Memorial Day
    assert date(2026, 9, 8) in y26 and date(2026, 10, 13) in y26  # Labor / Columbus Day
    assert date(2025, 10, 13) not in calendar and date(2025, 11, 17) in calendar  # 2025 lapse
    assert date(2027, 4, 5) in calendar


def test_detect_due_on_monday_and_no_stale_alarm_off_season(calendar):
    have = {"2026-11-02"}
    st = weekly_due(calendar, IN_SEASON, have, "16:00", 10, cadence_days=7)
    assert st.due == date(2026, 11, 9) and st.missing and not st.problems
    # Tuesday catch-up window: still missing, not yet overdue.
    tue = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)
    assert weekly_due(calendar, tue, have, "16:00", 10).problems == []
    # February: nothing due since November 30, the final release is not "stale".
    feb = datetime(2027, 2, 15, 15, 0, tzinfo=UTC)
    st = weekly_due(calendar, feb, {"2026-11-30"}, "16:00", 10, cadence_days=7)
    assert not st.missing and st.problems == []
    # A real gap during the season still raises the alarm.
    st = weekly_due(calendar, IN_SEASON, {"2026-10-05"}, "16:00", 10, cadence_days=7)
    assert any("stale" in p for p in st.problems)


def test_registry_entry(config_dir):
    c = load_registry(config_dir).get("crop_progress")
    assert c.enabled and c.seasonal and c.release_time_et == "16:00" and c.cadence == "weekly"
    assert c.release_key_format == "date"


@respx.mock
def test_ingest_page0_stores_zips_from_files(tmp_path, cfg):
    page = json.loads((FX / "esmis_page0.json").read_text(encoding="utf-8"))
    respx.get(URL, params={"page": "0"}).mock(return_value=httpx.Response(200, json=page))
    for it in page["results"]:
        z = next(f for f in it["files"] if f.endswith(".zip"))
        key = it["release_datetime"][:10]
        body = zip_bytes(key) if (FX / f"{key}.zip").exists() else zip_bytes("2026-10-26")
        respx.get(z).mock(return_value=httpx.Response(200, content=body))
    store = BronzeStore(tmp_path, Manifest(), "crop_progress", "16:00")
    with httpx.Client() as c:
        r = ingest_zips(
            c, store, cfg, title="Crop Progress", log_prefix="cp", error=CropProgressError,
            pause_s=0,
        )  # fmt: skip
    assert r.ingested[-1] == "2026-11-02" and len(r.ingested) == 3
    e = store.entries["2026-11-02"]
    assert e.url and e.url.endswith("prog4426.zip") and e.file == "crop_progress/2026-11-02.zip"


# ------------------------------------------------------------------ season state


def test_season_state_in_season_and_closed(calendar):
    assert cp.season_info("2026-11-02", calendar, IN_SEASON).state == "in_season"
    # The final scheduled release (Nov 30) ingested: closed the same evening.
    final = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)
    assert cp.season_info("2026-11-30", calendar, final).state == "closed"
    # Final release never arrived: closed a week after its date.
    si = cp.season_info("2026-11-23", calendar, OFF_SEASON)
    assert si.state == "closed" and si.last_scheduled == date(2026, 11, 30)
    # January-March: last year's season is closed.
    jan = datetime(2027, 1, 20, tzinfo=UTC)
    assert cp.season_info("2026-11-30", calendar, jan).state == "closed"
    # The new season opens with its first April release.
    apr = datetime(2027, 4, 6, 1, 0, tzinfo=UTC)
    assert cp.season_info("2027-04-05", calendar, apr).state == "in_season"


# ------------------------------------------------------------------ insights C1–C3


@pytest.fixture
def con():
    c = duckdb.connect()
    for name in ("fct_crop_condition", "fct_crop_progress_weekly"):
        c.execute(
            f"create table {name} as select * from read_parquet('{(FX / name).as_posix()}.parquet')"
        )
    dr = FX.parent / "nass_dim_release.parquet"
    c.execute(f"create table dim_release as select * from read_parquet('{dr.as_posix()}')")
    yield c
    c.close()


@pytest.fixture
def stage_order(cfg) -> dict[str, list[str]]:
    return {c: cfg.stage_order(c) for c in cfg.stages}


def _gated(insights: list[Insight], now: datetime, con) -> list[Insight]:
    from usda_reports.insights.engine import release_index

    g = Gates(stale_after_days={"crop_progress": 17, "grain_stocks": 192, "wasde": 76})
    return [gates_mod.apply(i, g, now, release_index(con)) for i in insights]


def test_in_season_c2_uses_nass_average_as_published(con, calendar, stage_order):
    si = cp.season_info(cp.latest_release_key(con) or "", calendar, IN_SEASON)
    assert si.state == "in_season"
    c2 = {i.id: i for i in _gated(cp.c2_stage_pace(con, si, stage_order), IN_SEASON, con)}
    corn = c2["C2:corn"]
    assert corn.params["stage"] == "harvested" and corn.params["value_pct"] == 74
    assert corn.params["nass_5yr_avg_pct"] == 77 and corn.params["pace_vs_5yr_pp"] == -3
    assert corn.params["position"] == "behind" and corn.params["avg_years"] == "2021-2025"
    assert (
        corn.n == 5
        and "small_sample" in corn.caveats
        and corn.window == "nass_published_5yr_average"
    )
    assert "nass_5yr_average_as_published" in corn.caveats
    assert c2["C2:winter_wheat"].params["stage"] == "emerged"  # in progress, after planted
    assert corn.suppressed_reason is None
    # Spring wheat ended in September: stale in November.
    assert c2["C2:spring_wheat"].suppressed_reason == "stale_input"


def test_in_season_c1_c3_own_5yr_and_small_samples_suppressed(con, calendar):
    si = cp.season_info("2026-11-02", calendar, IN_SEASON)
    c1 = {i.id: i for i in _gated(cp.c1_good_excellent(con, si), IN_SEASON, con)}
    ww = c1["C1:winter_wheat"]
    assert ww.params["week_ending"] == "2026-11-01" and ww.params["ge_pct"] == 44
    # No report on 2025-11-03 (funding lapse): only 4 of the 5 seasons match ±3 days.
    assert ww.n == 4 and ww.suppressed_reason == "n_below_min"
    assert len(ww.params["history"]) == 4 and "winter_wheat_fall_ratings_next_crop" in ww.caveats
    assert ww.window == "prior_5_seasons_same_week_doy_pm3"
    corn = c1["C1:corn"]
    assert corn.n == 0 and corn.suppressed_reason == "n_below_min" and corn.params["k"] is None
    c3 = {i.id: i for i in cp.c3_condition_index(con, si)}
    assert c3["C3:winter_wheat"].params["ci"] == pytest.approx(
        (1 * 5 + 2 * 13 + 3 * 38 + 4 * 38 + 5 * 6) / 100
    )


def test_off_season_c1_final_rating_not_stale_c2_c3_closed(con, calendar, stage_order):
    si = cp.season_info("2026-11-02", calendar, OFF_SEASON)
    assert si.state == "closed"
    c1 = {i.id: i for i in _gated(cp.c1_good_excellent(con, si), OFF_SEASON, con)}
    corn = c1["C1:corn"]
    assert corn.params["season_state"] == "closed" and corn.params["final"] is True
    assert corn.window == "prior_5_seasons_final_rating" and corn.n == 5
    assert corn.suppressed_reason is None  # exempt from the staleness gate
    assert "own_5yr_final_rating" in corn.caveats
    assert [h["season"] for h in corn.params["history"]] == [2021, 2022, 2023, 2024, 2025]
    c2 = _gated(cp.c2_stage_pace(con, si, stage_order), OFF_SEASON, con)
    c3 = _gated(cp.c3_condition_index(con, si), OFF_SEASON, con)
    assert {i.suppressed_reason for i in c2 + c3} == {"season_closed"}


def _card(rule: str, crop: str, **params) -> Insight:
    return Insight(
        id=f"{rule}:{crop}", rule=rule, report_id="crop_progress",  # type: ignore[arg-type]
        commodity_id="wheat" if "wheat" in crop else crop,
        kind={"C1": "good_excellent", "C2": "stage_pace", "C3": "condition_index"}[rule],  # type: ignore[arg-type]
        params={"crop": crop, **params}, n=5, window="w", robustness="robust",
        inputs=[InputRef(report_id="crop_progress", release_key="2026-11-02")],
        as_of="2026-11-02T21:00:00Z",
    )  # fmt: skip


def test_crop_progress_card_and_home_hidden_dec_to_mar():
    c2 = _card("C2", "corn", pace_vs_5yr_pp=-3.0)
    c2b = _card("C2", "soybeans", pace_vs_5yr_pp=4.0)
    c1 = _card("C1", "corn", position="above", outside_distance=0.2, season_state="in_season")
    c3 = _card("C3", "corn", position="above", outside_distance=0.5, season_state="in_season")
    assert crop_progress_card([c2, c2b]) == c2b  # largest gap to NASS's average
    assert crop_progress_card([c2, c1, c3]) == c3  # furthest outside the 5-year range
    closed = _card("C1", "winter_wheat", season_state="closed")
    assert crop_progress_card([closed, c3]) == closed
    hidden = {"crop_progress": [12, 1, 2, 3]}
    assert home_cards([closed], datetime(2026, 12, 15, tzinfo=UTC), hidden) == []
    assert home_cards([closed], datetime(2026, 11, 30, tzinfo=UTC), hidden) == [closed.id]


def test_missed_since_marks_the_off_season(config_dir):
    from usda_reports.detect import missed_since

    cfg = load_registry(config_dir).get("crop_progress")
    cal = config_dir / "calendars" / "crop_progress.yaml"
    # February after the final November release: nothing was due, so build.json is not stale.
    assert missed_since(cal, "2026-11-30", datetime(2027, 2, 15, tzinfo=UTC), cfg) == []
    # In season, a missing Monday is a missed release.
    assert missed_since(cal, "2026-10-26", IN_SEASON, cfg) == [date(2026, 11, 2), date(2026, 11, 9)]
