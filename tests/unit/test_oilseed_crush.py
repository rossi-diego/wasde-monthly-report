"""NASS Fats & Oils (oilseed crush): ESMIS client, NASS CSV grammar, parser, ingest, insights
F1–F3 and the crush page JSON. Fixtures are real ESMIS zips and a slice of the gold marts
recorded from the 2026-11-09 local run (no network)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import httpx
import pandas as pd
import pytest
import respx

from usda_reports.bronze.store import BronzeStore, sha256
from usda_reports.core.config import Settings
from usda_reports.core.contracts import Contract
from usda_reports.core.manifest import Manifest
from usda_reports.core.registry import load_registry
from usda_reports.core.vocab import UnseenLabelError
from usda_reports.nass_common.csv_tables import (
    NassCsvError,
    find_tables,
    parse_nass_csv,
    parse_value,
)
from usda_reports.nass_common.esmis import fetch_items, parse_items
from usda_reports.nass_common.zipfetch import NassZipError, is_zip, read_member
from usda_reports.reports.oilseed_crush.ingest import ingest, releases
from usda_reports.reports.oilseed_crush.parse import (
    StoredRelease,
    build_frame,
    column_role,
    market_year,
    parse_release,
    title_month,
    validate,
)
from usda_reports.reports.oilseed_crush.source import NassError, SourceConfig

FX = Path(__file__).resolve().parents[1] / "fixtures" / "oilseed_crush"
URL = "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/FatsOils"


@pytest.fixture
def cfg(config_dir: Path) -> SourceConfig:
    return SourceConfig.load(config_dir / "reports" / "oilseed_crush" / "source.yaml")


def zip_bytes(key: str) -> bytes:
    return (FX / f"{key}.zip").read_bytes()


# ------------------------------------------------------------------ nass_common


def test_parse_value_symbols():
    assert parse_value("6,148,544") == (6148544.0, None)
    assert parse_value("(D)") == (None, "D")
    assert parse_value("-") == (0.0, "zero")
    assert parse_value("") == (None, None)
    with pytest.raises(NassCsvError):
        parse_value("n/a")


def test_nass_grammar_tables_blocks_and_cp1252():
    _, data = read_member(zip_bytes("2026-11-02"), "*_all_tables.csv")
    tables = parse_nass_csv(data)
    soy = find_tables(
        tables, "Soybean Crushing, Production, Consumption and Stocks - United States"
    )
    assert len(soy) == 1 and soy[0].number == "1"
    # The en dash of the title is decoded from Windows-1252.
    assert "–" in soy[0].title
    regional = next(t for t in tables if t.number == "10")
    assert len(regional.blocks) == 5  # one block per regional series
    assert regional.blocks[0].units[0][1] == "(tons)"
    with pytest.raises(NassCsvError):
        parse_nass_csv(b"1,x,bad\n")


def test_esmis_items_keep_api_order_and_files(cfg):
    page = json.loads((FX / "esmis_page0.json").read_text())
    items = parse_items(page)
    assert [i.release_key for i in items] == ["2026-11-02", "2026-10-01", "2026-09-01"]
    assert items[0].file_with_suffix(".zip", ".ZIP").endswith("cafo1126.zip")


@respx.mock
def test_esmis_paging_starts_at_page_zero():
    p0 = respx.get(URL, params={"page": "0"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "pager": {"total_pages": 2},
                "results": [{"id": 2, "release_datetime": "2026-11-02T12:00:00+0000", "files": []}],
            },
        )
    )
    p1 = respx.get(URL, params={"page": "1"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "pager": {"total_pages": 2},
                "results": [{"id": 1, "release_datetime": "2026-10-01T12:00:00+0000", "files": []}],
            },
        )
    )
    with httpx.Client() as c:
        items = fetch_items(c, URL)
    assert p0.called and p1.called and len(items) == 2
    with httpx.Client() as c:
        assert len(fetch_items(c, URL, max_pages=1)) == 1


def test_zip_checks():
    assert is_zip(zip_bytes("2026-11-02"))
    assert not is_zip(b"<html>blocked</html>")
    with pytest.raises(NassZipError):
        read_member(zip_bytes("2026-11-02"), "*.nothing")


# ------------------------------------------------------------------ parser


def test_market_year_and_roles():
    assert market_year(date(2026, 9, 1)) == ("2026/27", 2026, 1)
    assert market_year(date(2026, 8, 1)) == ("2025/26", 2025, 12)
    assert column_role(date(2025, 9, 1), date(2026, 9, 1)) == "year_ago"
    assert column_role(date(2026, 8, 1), date(2026, 9, 1)) == "previous"
    assert title_month("…: May 2015 – August 2015") == date(2015, 8, 1)
    assert title_month("…: September 2026 with Comparisons") == date(2026, 9, 1)


def test_parse_latest_release_matches_published_text(cfg):
    df = parse_release(zip_bytes("2026-11-02"), cfg, "2026-11-02")
    cur = df[df.column_role == "current"].set_index("metric")["value"]
    # cafo1126.txt: "5.96 million tons (199 million bushels) in September 2026".
    assert cur["crushed_st"] == 5964861
    assert round(cur["crushed_st"] * 33.3333 / 1e6) == 199
    assert cur["crude_oil_produced_klb"] == 2309806
    assert cur["meal_produced_st"] == 4187161
    assert set(df.unit_id) == {"short_ton", "klb"}
    assert set(df.column_role) == {"current", "previous", "year_ago"}
    assert (df.market_year[df.month == date(2026, 9, 1)] == "2026/27").all()


def test_parse_first_release_prints_four_months(cfg):
    df = parse_release(zip_bytes("2015-10-01"), cfg, "2015-10-01")
    assert sorted(set(df.month)) == [date(2015, m, 1) for m in (5, 6, 7, 8)]
    assert set(df.column_role) == {"current", "previous", "earlier"}


def test_header_typo_is_fixed_only_where_configured(cfg):
    df = parse_release(zip_bytes("2022-03-01"), cfg, "2022-03-01")
    assert date(2021, 12, 1) in set(df.month) and date(2022, 12, 1) not in set(df.month)
    with pytest.raises(NassError, match="not in order"):
        parse_release(zip_bytes("2022-03-01"), cfg, "2099-01-01")


def test_unseen_row_label_fails(cfg):
    _, data = read_member(zip_bytes("2026-11-02"), "*_all_tables.csv")
    bad = data.replace(b'"Millfeed produced"', b'"Something new"')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("cafo_all_tables.csv", bad)
    with pytest.raises(UnseenLabelError, match="Something new"):
        parse_release(buf.getvalue(), cfg, "2026-11-02")


def test_build_frame_envelope_and_contract(cfg, config_dir):
    rels = [
        StoredRelease(k, sha256(zip_bytes(k)), 1, f"https://esmis/{k}.zip", zip_bytes(k))
        for k in ("2025-12-10", "2026-11-02")
    ]
    silver = build_frame(rels, cfg, "15:00")
    validate(silver, Contract.load(config_dir / "contracts" / "oilseed_crush.yaml"))
    assert set(silver.report_id) == {"oilseed_crush"}
    assert set(silver.vintage_quality) == {"as_published"}
    ts = silver[silver.release_key == "2026-11-02"].release_ts_utc.iloc[0]
    assert ts == pd.Timestamp("2026-11-02 20:00", tz="UTC")  # 15:00 ET (EST)
    # September 2025 was first printed as the previous month of the 2025-12-10 release.
    sep = silver[(silver.month == date(2025, 9, 1)) & (silver.metric == "crushed_st")]
    assert set(sep.column_role) == {"previous", "year_ago"}


def test_lag_check_rejects_a_misdated_release(cfg):
    rel = StoredRelease("2027-06-01", "0" * 64, 1, None, zip_bytes("2026-11-02"))
    with pytest.raises(NassError, match="months earlier"):
        build_frame([rel], cfg)


# ------------------------------------------------------------------ ingest


def _esmis(items: list[dict]) -> dict:
    return {"pager": {"total_pages": 1}, "results": items}


def _item(rid: int, day: str, files: list[str]) -> dict:
    return {"id": rid, "release_datetime": f"{day}T12:00:00+0000", "files": files}


@respx.mock
def test_ingest_stores_zips_skips_notices_and_new_editions(tmp_path, cfg):
    z1 = "https://esmis/a/cafo1026.zip"
    z2 = "https://esmis/b/cafo1126.zip"
    notice = json.loads((FX / "esmis_notice.json").read_text())["results"]
    respx.get(URL, params={"page": "0"}).mock(
        return_value=httpx.Response(
            200,
            json=_esmis([_item(3, "2026-11-02", [z2]), _item(2, "2025-12-10", [z1]), *notice]),
        )
    )
    respx.get(z1).mock(return_value=httpx.Response(200, content=zip_bytes("2025-12-10")))
    route2 = respx.get(z2).mock(return_value=httpx.Response(200, content=zip_bytes("2026-11-02")))
    manifest = Manifest()
    store = BronzeStore(tmp_path, manifest, "oilseed_crush", "15:00")
    checked: list[str] = []
    cfg2 = cfg.model_copy(update={"history_start": "2015-10-01"})
    with httpx.Client() as c:
        r = ingest(c, store, cfg2, check=lambda k, d: checked.append(k), pause_s=0)
    assert r.ingested == ["2025-12-10", "2026-11-02"] and r.skipped == ["2019-01-02"]
    assert checked == r.ingested
    e = store.entries["2026-11-02"]
    assert e.file == "oilseed_crush/2026-11-02.zip" and e.url == z2
    assert e.release_ts_utc == "2026-11-02T20:00:00+00:00"
    assert store.entries["2019-01-02"].status == "skipped"
    # Same bytes again: nothing new. Changed bytes of a recent release: a new edition.
    with httpx.Client() as c:
        assert ingest(c, store, cfg2, pause_s=0).ingested == []
    route2.mock(return_value=httpx.Response(200, content=zip_bytes("2024-07-01")))
    with httpx.Client() as c:
        assert ingest(c, store, cfg2, pause_s=0).ingested == ["2026-11-02"]
    assert store.entries["2026-11-02"].edition == 2


@respx.mock
def test_ingest_rejects_non_zip_before_bronze(tmp_path, cfg):
    z = "https://esmis/x/cafo1126.zip"
    respx.get(URL, params={"page": "0"}).mock(
        return_value=httpx.Response(200, json=_esmis([_item(1, "2026-11-02", [z])]))
    )
    respx.get(z).mock(return_value=httpx.Response(200, content=b"<html>Access denied</html>"))
    store = BronzeStore(tmp_path, Manifest(), "oilseed_crush", "15:00")
    with httpx.Client() as c, pytest.raises(NassError):
        ingest(c, store, cfg, pause_s=0)
    assert store.entries == {}


def test_releases_filter_history_and_duplicates(cfg):
    items = parse_items(
        _esmis(
            [
                _item(5, "2015-09-01", ["x.zip"]),
                _item(6, "2016-01-04", ["a.zip"]),
                _item(9, "2016-01-04", ["b.zip"]),
            ]
        )
    )
    out = releases(items, cfg)
    assert [i.release_id for i in out] == ["9"]


def test_spec_rejects_bad_zip_and_builds_last_good(tmp_path, config_dir):
    settings = Settings(data_dir=tmp_path / "data", config_dir=config_dir)
    spec = load_registry(config_dir).spec("oilseed_crush", settings)
    assert spec.isolated and spec.config.release_key_format == "date"
    with pytest.raises(NassError, match="rejected before bronze"):
        spec.check_release("2026-11-02", b"PK not a zip")  # type: ignore[attr-defined]
    manifest = Manifest()
    store = BronzeStore(settings.bronze_dir, manifest, "oilseed_crush", "15:00")
    for k in ("2024-06-03", "2024-07-01"):
        store.put(k, zip_bytes(k), source="esmis_zip", url=f"u/{k}", release_date=k)
    good = spec.build_silver(manifest)
    assert good.release_key.nunique() == 2
    # A tampered newest file: the full build fails, the fallback keeps the older release.
    (settings.bronze_dir / "oilseed_crush" / "2024-07-01.zip").write_bytes(b"tampered")
    with pytest.raises(spec.source_errors()):
        spec.build_silver(manifest)
    assert spec.build_silver_last_good(manifest).release_key.unique().tolist() == ["2024-06-03"]


def test_due_gate_for_a_date_keyed_monthly_report(config_dir):
    from usda_reports.core.calendar import load_calendar
    from usda_reports.detect import weekly_due

    dates = load_calendar(config_dir / "calendars" / "oilseed_crush.yaml")
    assert date(2025, 11, 21) in dates and date(2019, 1, 2) not in dates
    # 2026-12-01 15:00 ET = 20:00 UTC: due one minute later, not before.
    before = weekly_due(
        dates,
        datetime(2026, 12, 1, 19, 59, tzinfo=UTC),
        {"2026-11-02"},
        "15:00",
        45,
        cadence_days=31,
    )
    after = weekly_due(
        dates,
        datetime(2026, 12, 1, 20, 1, tzinfo=UTC),
        {"2026-11-02"},
        "15:00",
        45,
        cadence_days=31,
    )
    assert not before.missing and after.missing and after.due == date(2026, 12, 1)
    assert not after.problems
    late = weekly_due(
        dates,
        datetime(2026, 12, 7, 12, tzinfo=UTC),
        {"2026-11-02"},
        "15:00",
        45,
        3,
        cadence_days=31,
    )
    assert any("still missing" in p for p in late.problems)


# ------------------------------------------------------------------ insights and page JSON


@pytest.fixture
def gold() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for t in ("fct_crush_pace", "fct_soy_crush_monthly"):
        con.execute(
            f"create table {t} as select * from read_parquet('{(FX / f'{t}.parquet').as_posix()}')"
        )
    yield con
    con.close()


def test_f1_f2_f3_from_recorded_gold(gold):
    from usda_reports.insights.rules import crush

    pace = crush.pace_frame(gold)
    f1 = crush.f1_crush_pace(pace)[0]
    assert (
        f1.id == "F1:soybeans" and f1.report_id == "oilseed_crush" and f1.suppressed_reason is None
    )
    p = f1.params
    assert (
        p["market_year"] == "2026/27"
        and p["month"] == "2026-09-01"
        and p["wasde_release_key"] == "2026-10"
    )
    assert p["pct"] == pytest.approx(p["cum_bu"] / p["target_bu"], abs=1e-4)
    assert p["cum_bu"] == pytest.approx(5964861 * 33.3333)
    assert f1.n == 5 and [h["market_year"] for h in p["history"]] == [
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
        "2025/26",
    ]
    assert p["position"] == "below" and p["history_start"] == "2015-10"
    assert "crush_history_from_2015" in f1.caveats
    # History is point in time: 2025/26 September was first printed on 2025-12-10.
    assert p["history"][-1]["wasde_release_key"] == "2025-12"
    assert {r.report_id for r in f1.inputs} == {"oilseed_crush", "wasde"}

    f2 = crush.f2_required_monthly_crush(pace)[0]
    assert f2.params["months_remaining"] == 11 and f2.n == 11
    assert f2.params["required_monthly_bu"] == pytest.approx(
        (f2.params["target_bu"] - f2.params["cum_bu"]) / 11, abs=1
    )
    aug = pace[pace.month_of_my == 12].tail(1)
    assert crush.f2_required_monthly_crush(aug)[0].suppressed_reason == "months_remaining_below_min"
    # Plan §6: no card with n < 5. With 4 months left (data month April) F2 is suppressed; with 5
    # it passes the default gates (no min_n exception for F2).
    from usda_reports.insights import gates as gates_mod
    from usda_reports.insights.schema import Gates

    now = datetime(2026, 11, 9, tzinfo=UTC)
    apr = pace[pace.month_of_my == 8].tail(1)
    f2_apr = crush.f2_required_monthly_crush(apr, Gates().f2_min_months_remaining)[0]
    assert f2_apr.params["months_remaining"] == 4
    assert gates_mod.apply(f2_apr, Gates(), now, {}).suppressed_reason is not None
    mar = pace[pace.month_of_my == 7].tail(1)
    f2_mar = crush.f2_required_monthly_crush(mar, Gates().f2_min_months_remaining)[0]
    assert f2_mar.params["months_remaining"] == 5 and f2_mar.n == 5
    assert f2_mar.suppressed_reason is None

    f3 = crush.f3_oil_yield(pace)[0]
    assert f3.params["oil_yield_lb_bu"] == pytest.approx(
        2309806 * 1000 / (5964861 * 33.3333), abs=1e-4
    )
    assert f3.params["wasde_implied_yield_lb_bu"] is not None and f3.n == 5
    assert "wasde_oil_year_oct_sep" in f3.caveats


def test_crush_card_is_the_most_extreme_f1_or_f3(gold):
    from usda_reports.insights import gates as gates_mod
    from usda_reports.insights.hero import crush_card, home_cards
    from usda_reports.insights.rules import crush
    from usda_reports.insights.schema import Gates

    pace = crush.pace_frame(gold)
    raw = (
        crush.f1_crush_pace(pace) + crush.f2_required_monthly_crush(pace) + crush.f3_oil_yield(pace)
    )
    now = datetime(2026, 11, 9, tzinfo=UTC)
    out = [gates_mod.apply(i, Gates(), now, {}, min_n=None) for i in raw]
    card = crush_card(out)
    assert card is not None and card.rule in ("F1", "F3")
    best = max(
        (i for i in out if i.rule in ("F1", "F3")), key=lambda i: i.params["outside_distance"]
    )
    assert card.id == best.id
    assert card.id in home_cards(out)
    # Suppressed insights never become the card.
    sup = [i.model_copy(update={"suppressed_reason": "stale_input"}) for i in out]
    assert crush_card(sup) is None


def test_crush_page_json(gold, tmp_path):
    from usda_reports.publish.web_crush import build_crush

    idx = build_crush(gold, tmp_path, "2026-12-01")
    assert idx is not None and idx["latest"]["release_key"] == "2026-11-02"
    d = json.loads((tmp_path / "reports" / "oilseed_crush" / "soybeans.json").read_text())
    assert d["history_start"] == "2015-10" and d["market_year"] == "2026/27"
    assert d["kpis"]["month_crushed_st"] == 5964861 and d["next_release"] == "2026-12-01"
    assert d["pace"]["basis"] == "pct_of_usda_projection_at_the_time"
    assert [s["market_year"] for s in d["pace"]["series"]][-1] == "2026/27"
    assert len(d["pace"]["band"]) == 12 and all(b[4] == 5 for b in d["pace"]["band"])
    assert len(d["remaining"]["last_my_months"]) == 11 and len(d["monthly"]) == 24
    assert "nopa" not in json.dumps(d).lower()


def test_crush_shares_keep_full_precision(gold, tmp_path):
    """0.071521 must print 7.2%: shares are published at 6 dp, never pre-rounded to 4."""
    from usda_reports.insights.rules import crush
    from usda_reports.publish.web_crush import build_crush

    pace = crush.pace_frame(gold)
    cur = crush.current_row(pace)
    true = float(cur.cum_bu) / float(cur.wasde_crush_bu)
    f1 = crush.f1_crush_pace(pace)[0]
    assert f1.params["pct"] == pytest.approx(true, abs=1e-6)
    # The file the browser reads (the JSON writer rounds floats; it must keep 6 dp here).
    build_crush(gold, tmp_path, None)
    d = json.loads((tmp_path / "reports" / "oilseed_crush" / "soybeans.json").read_text())
    assert d["kpis"]["pct_of_target"] == pytest.approx(true, abs=1e-6)
    assert d["kpis"]["pct_of_target"] != round(true, 4)
    # The formatter rounds once: (x*100).toFixed(1). 0.0715 would give 7.1; the 6-dp value 7.2.
    assert f"{f1.params['pct'] * 100:.1f}" == f"{true * 100:.1f}"
    assert f"{0.071521 * 100:.1f}" == "7.2" and f"{round(0.071521, 6) * 100:.1f}" == "7.2"
