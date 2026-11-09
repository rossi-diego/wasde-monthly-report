"""Crop Progress and Grain Stocks through dbt and publish on the mini build (``built``).

The mini build holds two recorded Crop Progress releases (2025-09-02 and 2025-09-08) and two
Grain Stocks releases (2025-03-31, 2025-06-30) next to a corn-only WASDE (2024-04/05). The
marts, the point-in-time cross marts and every dbt test on them run; the insights are honest
about the tiny history (n below the minimum, no as-of WASDE for 2025); the report JSON,
the commodity lens, meta.json, the catalogue and datapackage carry both reports; and the
committed catalogue schema snapshot matches the models.
"""

from __future__ import annotations

import json

import duckdb
import pytest

from usda_reports.core.config import PROJECT_ROOT, Settings
from usda_reports.insights.schema import InsightsDoc
from usda_reports.publish.contract import release_contract_problems
from usda_reports.publish.schema_diff import compare, load_snapshot, snapshot_from_duckdb

pytest.importorskip("dbt")


@pytest.fixture(scope="module")
def con(built: Settings):
    c = duckdb.connect(str(built.duckdb_path))
    yield c
    c.close()


def test_marts_and_dim_release(con):
    rel = dict(con.execute("select report_id, count(*) from dim_release group by 1").fetchall())
    assert rel["crop_progress"] == 2 and rel["grain_stocks"] == 2
    ts = con.execute(
        "select strftime(release_ts_utc at time zone 'UTC', '%H:%M') from dim_release "
        "where report_id = 'crop_progress' and release_key = '2025-09-08'"
    ).fetchone()
    assert ts == ("20:00",)  # 16:00 ET in summer (EDT)
    weeks = con.execute(
        "select distinct week_ending::varchar from fct_crop_progress_weekly order by 1"
    ).fetchall()
    assert weeks == [("2025-08-31",), ("2025-09-07",)]
    cond = con.execute(
        "select ge_pct, ci, n_5yr from fct_crop_condition where crop = 'corn' "
        "and week_ending = '2025-09-07'"
    ).fetchone()
    assert cond is not None and 0 < cond[0] < 100 and 1 <= cond[1] <= 5 and cond[2] == 0
    stocks = con.execute(
        "select total_kbu, first_release_key, quarter_of_my from fct_grain_stocks_quarterly "
        "where commodity_id = 'corn' and as_of_date = '2025-06-01'"
    ).fetchone()
    assert stocks is not None and stocks[1] == "2025-06-30" and stocks[2] == 3
    g1 = con.execute(
        "select market_year, wasde_release_key from fct_stocks_vs_wasde "
        "where commodity_id = 'wheat' and as_of_date = '2025-06-01'"
    ).fetchone()
    assert g1 == ("2024/25", None)  # no wheat WASDE in the corn-only fixture: no look-ahead


def test_dbt_tests_on_cut_c_models(built: Settings):
    from usda_reports.gold import run_dbt

    select = (
        "stg_crop_progress stg_grain_stocks fct_crop_progress_weekly fct_crop_condition "
        "fct_grain_stocks_quarterly fct_stocks_vs_wasde fct_stocks_disappearance "
        "fct_commodity_lens dim_release"
    )
    assert run_dbt(built, command="test", select=select, fresh=False) == 0
    results = json.loads(
        (built.gold_dir / "dbt_target" / "run_results.json").read_text(encoding="utf-8")
    )["results"]
    ids = {r["unique_id"] for r in results}
    for name in (
        "assert_crop_progress_monotonic",
        "assert_crop_progress_pct_range",
        "assert_crop_condition_sums_100",
        "assert_grain_stocks_positions_sum",
        "stocks_vs_wasde_asof_same_timestamp_boundary",
        "stocks_disappearance_harvest_quarter",
        "crop_condition_5yr_same_week_by_day_of_year",
    ):
        assert any(name in i for i in ids), name
    assert sum("assert_no_lookahead" in i and "stocks" in i for i in ids) == 3
    assert all(r["status"] in ("pass", "warn", "success") for r in results)


def test_insights_are_honest_about_the_small_history(built: Settings):
    raw = json.loads((built.web_data_dir / "insights.json").read_text(encoding="utf-8"))
    doc = InsightsDoc.model_validate(raw)
    by_rule = {i.rule for i in doc.insights}
    assert {"C1", "C2", "C3", "G2", "G3"} <= by_rule
    for i in doc.insights:
        if i.rule in ("C1", "C3", "G2", "G3"):
            assert i.suppressed_reason is not None  # n < 5 everywhere in the mini build
        if i.n is not None and i.n < 10:
            assert "small_sample" in i.caveats
    c2 = next(i for i in doc.insights if i.id == "C2:corn")
    assert c2.params["season_state"] == "in_season" and c2.n == 5
    assert doc.seasons["crop_progress"].state == "in_season"
    g1 = [i for i in doc.insights if i.rule == "G1"]
    assert all(i.suppressed_reason == "asof_missing" for i in g1)
    assert len(doc.home_cards) <= 5


def test_report_json_lens_and_meta(built: Settings):
    web = built.web_data_dir
    cp = json.loads((web / "reports" / "crop_progress" / "index.json").read_text("utf-8"))
    assert cp["latest"]["release_key"] == "2025-09-08" and cp["season"]["state"] == "in_season"
    corn = json.loads((web / "reports" / "crop_progress" / "corn.json").read_text("utf-8"))
    assert corn["latest"]["week_ending"] == "2025-09-07" and corn["stages"]
    assert corn["ge"]["basis"] == "own_5yr_same_week_by_day_of_year"
    assert corn["stage_pace"]["basis"] == "nass_5yr_average_as_published"
    gs = json.loads((web / "reports" / "grain_stocks" / "corn.json").read_text("utf-8"))
    assert gs["latest"]["as_of_date"] == "2025-06-01" and gs["unit_id"] == "m_bu"
    lens = json.loads((web / "lens" / "corn.json").read_text("utf-8"))
    reports = {r["report_id"]: r for r in lens["reports"]}
    assert {"wasde", "crop_progress", "grain_stocks"} <= set(reports)
    assert all(r["release_key"] and r["release_ts_utc"] for r in lens["reports"])
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["reports"]["crop_progress"]["latest_release_key"] == "2025-09-08"
    assert meta["reports"]["grain_stocks"]["latest_release_key"] == "2025-06-30"
    # The Soy Outlook contract still holds with the new reports in meta.json.
    assets = ["meta.json", "manifest.json", "wasde_full.parquet"]
    assert release_contract_problems("data-2024-05", meta, assets) == []


def test_catalogue_datapackage_and_schema_snapshot(built: Settings, con):
    files = json.loads((built.publish_dir / "datasets.json").read_text(encoding="utf-8"))
    names = {f["file"] for f in files}
    for stem in ("crop_progress__weekly__v1", "crop_progress__condition__v1",
                 "grain_stocks__quarterly__v1", "cross__stocks_vs_wasde__v1"):  # fmt: skip
        assert f"{stem}.parquet" in names
    pkg = json.loads((built.publish_dir / "datapackage.json").read_text(encoding="utf-8"))
    res = {r["path"]: r for r in pkg["resources"]}
    assert res["grain_stocks__quarterly__v1.parquet"]["contract_enforced"] is True
    assert (
        "NASS (Grain Stocks)" in res["grain_stocks__quarterly__v1.parquet"]["licenses"][0]["title"]
    )
    assert any("CropProg" in s["path"] for s in pkg["sources"])
    # The committed snapshot (docs/schemas/catalog.schema.json) matches the models.
    committed = load_snapshot(PROJECT_ROOT / "docs" / "schemas" / "catalog.schema.json")
    current = snapshot_from_duckdb(con)
    assert current == committed, "run `usda-reports catalog-schema` and commit the snapshot"
    assert compare(committed, current).ok
