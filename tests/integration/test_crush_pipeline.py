"""NASS crush through dbt and publish on the mini build (``built``).

The mini build holds two recorded Fats & Oils releases (2024-06-03, 2024-07-01: April and May
2024 data) and a corn-only WASDE. MY 2023/24 is incomplete in those files, so the point-in-time
pace mart has no complete row and no soybean WASDE target exists: the crush page JSON is not
written and F1–F3 are absent, while the monthly mart, dim_release, the catalogue and every
crush dbt test still run.
"""

from __future__ import annotations

import json

import duckdb
import pytest

from usda_reports.core.config import Settings

pytest.importorskip("dbt")


@pytest.fixture(scope="module")
def con(built: Settings):
    c = duckdb.connect(str(built.duckdb_path))
    yield c
    c.close()


def test_monthly_mart_and_dim_release(con):
    rows = con.execute(
        "select month, crushed_st, crushed_bu, first_release_key, latest_release_key, is_revised "
        "from fct_soy_crush_monthly order by month"
    ).df()
    assert len(rows) >= 4
    may = rows[rows.month.astype(str) == "2024-05-01"].iloc[0]
    assert may.first_release_key == "2024-07-01"
    assert may.crushed_bu == pytest.approx(may.crushed_st * 33.3333)
    # April 2024: first printed on 2024-06-03, revised (or confirmed) by 2024-07-01.
    apr = rows[rows.month.astype(str) == "2024-04-01"].iloc[0]
    assert apr.first_release_key == "2024-06-03" and apr.latest_release_key == "2024-07-01"
    rel = dict(con.execute("select report_id, count(*) from dim_release group by 1").fetchall())
    assert rel["oilseed_crush"] == 2
    ts = con.execute(
        "select strftime(release_ts_utc at time zone 'UTC', '%H:%M') from dim_release "
        "where report_id = 'oilseed_crush' and release_key = '2024-07-01'"
    ).fetchone()
    assert ts == ("19:00",)  # 15:00 ET in summer (EDT)


def test_incomplete_year_gives_no_pace_and_no_insight(con, built: Settings):
    assert con.execute("select count(*) from fct_crush_pace").fetchone() == (0,)
    doc = json.loads((built.web_data_dir / "insights.json").read_text(encoding="utf-8"))
    assert not [i for i in doc["insights"] if i["rule"].startswith("F")]
    assert not (built.web_data_dir / "reports" / "oilseed_crush").exists()


def test_catalogue_and_meta_carry_crush(built: Settings):
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["reports"]["oilseed_crush"]["latest_release_key"] == "2024-07-01"
    assert {"data_release_tag", "next_release", "latest"} <= set(meta)
    files = json.loads((built.publish_dir / "datasets.json").read_text(encoding="utf-8"))
    names = {f["file"] for f in files}
    assert "oilseed_crush__monthly__v1.parquet" in names
    assert "cross__crush_pace__v1.parquet" not in names  # empty mart: skipped, never blocks
    cat = json.loads((built.web_data_dir / "catalog.json").read_text(encoding="utf-8"))
    assert "NASS" in cat["reports"]["oilseed_crush"]["licence"]
    pkg = json.loads((built.publish_dir / "datapackage.json").read_text(encoding="utf-8"))
    res = [r for r in pkg["resources"] if r["dataset"] == "monthly"]
    assert res and res[0]["contract_enforced"] is True
    fields = {f["name"]: f for f in res[0]["schema"]["fields"]}
    assert fields["oil_yield_lb_bu"]["description"].startswith("Crude oil extraction rate")


def test_dbt_tests_on_crush_models(built: Settings):
    from usda_reports.gold import run_dbt

    select = "stg_oilseed_crush fct_soy_crush_monthly fct_crush_pace dim_release"
    assert run_dbt(built, command="test", select=select, fresh=False) == 0
    results = json.loads(
        (built.gold_dir / "dbt_target" / "run_results.json").read_text(encoding="utf-8")
    )["results"]
    ids = {r["unique_id"] for r in results}
    assert any("crush_pace_asof_same_timestamp_boundary" in i for i in ids)
    assert sum("assert_no_lookahead" in i and "fct_crush_pace" in i for i in ids) == 3
    assert all(r["status"] in ("pass", "warn", "success") for r in results)
