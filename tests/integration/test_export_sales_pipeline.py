"""Export Sales + cross-report marts and publish outputs on the mini build (``built``).

The mini build has WASDE 2024-04/2024-05 (U.S./World corn only) and one fixture ESR pull from
2025-09-11 (5 commodities, 4 destinations). So corn has a point-in-time USDA target and the
other commodities do not, which exercises both the ASOF join and the suppression gates.
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from usda_reports.core.config import Settings
from usda_reports.insights.schema import InsightsDoc
from usda_reports.publish.contract import release_contract_problems

pytest.importorskip("dbt")


@pytest.fixture(scope="module")
def con(built: Settings):
    # Same configuration as the other in-process handles (dbt, publish).
    c = duckdb.connect(str(built.duckdb_path))
    yield c
    c.close()


def test_weekly_marts_and_dim_release(con):
    w = con.execute(
        "select count(*), count(distinct commodity_id), max(week_ending) from fct_export_sales_weekly"
    ).fetchone()
    assert w[0] > 0 and w[1] == 5 and str(w[2]) == "2025-09-04"
    t = con.execute(
        """select total_commitment_mt, accumulated_exports_mt + outstanding_sales_mt,
                  china_commitment_mt, unknown_commitment_mt, n_destinations
           from fct_export_sales_totals
           where commodity_id = 'soybeans' and week_ending = '2025-09-04'"""
    ).fetchone()
    assert t[0] == pytest.approx(t[1]) and t[2] > 0 and t[4] <= 4
    rel = dict(
        con.execute("select report_id, count(*) from dim_release group by report_id").fetchall()
    )
    assert rel["wasde"] == 2 and rel["export_sales"] > 50
    latest = con.execute(
        "select release_key from dim_release where report_id='export_sales' and is_latest"
    ).fetchone()
    assert latest == ("2025-09-11",)


def test_pace_is_point_in_time(con):
    df = con.execute(
        """select market_year, week_ending, release_ts_utc, wasde_release_key,
                  wasde_release_ts_utc, wasde_unit_id, wasde_exports_native, wasde_exports_mt,
                  pct_of_target
           from fct_export_pace where commodity_id = 'corn' order by week_ending"""
    ).df()
    with_target = df[df.wasde_release_key.notna()]
    assert len(with_target)
    assert (with_target.wasde_release_ts_utc <= with_target.release_ts_utc).all()
    # Weeks released before the first fixture WASDE (2024-04-11) have no target.
    early = df[df.release_ts_utc < pd.Timestamp("2024-04-11 16:00", tz="UTC")]
    assert early.wasde_release_key.isna().all()
    # 2024/25 weeks (released after 2024-05-10) use the May report; mil bu → MT.
    cur = with_target[with_target.market_year == "2024/25"].iloc[-1]
    assert cur.wasde_release_key == "2024-05" and cur.wasde_unit_id == "m_bu"
    assert cur.wasde_exports_mt == pytest.approx(cur.wasde_exports_native * 25401.4057138)
    soy = con.execute(
        "select count(*) from fct_export_pace where commodity_id='soybeans' and wasde_release_key is not null"
    ).fetchone()
    assert soy == (0,)  # no soybean WASDE in the fixture → no target, never a later one


def test_dbt_tests_on_esr_and_cross_models(built: Settings):
    """Contracts, assert_no_lookahead, the monotonic and uniqueness tests and the
    same-timestamp ASOF boundary unit test, on the built mini warehouse."""
    from usda_reports.gold import run_dbt

    select = (
        "stg_export_sales fct_export_sales_weekly fct_export_sales_totals int_wasde_asof "
        "fct_export_pace dim_country dim_release dim_unit"
    )
    assert run_dbt(built, command="test", select=select, fresh=False) == 0
    results = json.loads(
        (built.gold_dir / "dbt_target" / "run_results.json").read_text(encoding="utf-8")
    )["results"]
    ids = {r["unique_id"] for r in results}
    assert any("export_pace_asof_same_timestamp_boundary" in i for i in ids)
    assert any("assert_no_lookahead" in i for i in ids)
    assert any("assert_esr_accumulated_monotonic" in i for i in ids)
    assert all(r["status"] in ("pass", "warn", "success") for r in results)


def test_insights_json_is_params_only_and_gated(built: Settings):
    raw = json.loads((built.web_data_dir / "insights.json").read_text(encoding="utf-8"))
    doc = InsightsDoc.model_validate(raw)
    assert doc.data_tag == "data-2024-05"
    by = {i.id: i for i in doc.insights}
    # WASDE 2024-05 is long stale on 2025-09-12: every WASDE-based insight is suppressed.
    assert all(
        i.suppressed_reason is not None
        for i in doc.insights
        if any(r.report_id == "wasde" for r in i.inputs)
    )
    assert by["E1:soybeans"].suppressed_reason == "asof_missing"
    assert by["E1:corn"].params["wasde_release_key"] == "2024-05"
    assert by["E3:soybeans"].suppressed_reason == "n_below_min"  # one MY of history only
    assert by["E3:soybeans"].params["china_share"] is not None
    assert doc.hero.kind == "fallback" and doc.home_cards == []
    # No prose anywhere: params hold numbers, ids, dates and lists of those only.
    for i in doc.insights:
        for v in i.params.values():
            if isinstance(v, str):
                assert len(v) <= 40 and " " not in v, (i.id, v)


def test_export_sales_page_json(built: Settings):
    folder = built.web_data_dir / "reports" / "export_sales"
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in index["commodities"]] == [
        "soybeans",
        "corn",
        "wheat",
        "soybean_meal",
        "soybean_oil",
    ]
    assert index["latest"]["release_key"] == "2025-09-11"
    corn = json.loads((folder / "corn.json").read_text(encoding="utf-8"))
    assert corn["target"]["wasde_release_key"] == "2024-05"
    assert corn["pace"]["basis"] == "pct_of_usda_projection_at_the_time"
    assert [s["market_year"] for s in corn["pace"]["series"]] == ["2023/24", "2024/25"]
    assert corn["pace"]["series"][-1]["current"] is True
    dest = {r["country_id"] for r in corn["destinations"]["rows"]}
    assert dest <= {"china", "unknown", "mexico", "japan"} and "mexico" in dest
    soy = json.loads((folder / "soybeans.json").read_text(encoding="utf-8"))
    assert soy["target"]["exports_mt"] is None and soy["kpis"]["pct_of_target"] is None


def test_catalogue_datapackage_and_catalog(built: Settings):
    pub, web = built.publish_dir, built.web_data_dir
    for stem in (
        "export_sales__weekly__v1",
        "export_sales__by_country__v1",
        "cross__export_pace__v1",
    ):
        assert (pub / f"{stem}.parquet").stat().st_size > 0
        assert any(p.name.startswith(stem) and ".csv" in p.name for p in pub.iterdir())
    pkg = json.loads((pub / "datapackage.json").read_text(encoding="utf-8"))
    assert pkg["profile"] == "tabular-data-package"
    res = {r["path"]: r for r in pkg["resources"]}
    pace = res["cross__export_pace__v1.parquet"]
    assert pace["hash"].startswith("sha256:") and pace["rows"] > 0
    assert pace["contract_enforced"] is True and pace["schema_version"] == 1
    fields = {f["name"]: f for f in pace["schema"]["fields"]}
    assert fields["pct_of_target"]["type"] == "number"
    assert "wasde_exports_mt" in fields["pct_of_target"]["description"]
    assert fields["week_ending"]["type"] == "date"
    assert "wasde_full.parquet" not in res  # aliases are not separate resources
    assert res["export_sales__weekly__v1.parquet"]["licenses"][0]["title"].startswith(
        "US Government work"
    )
    catalog = json.loads((web / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["data_tag"] == "data-2024-05"
    files = {f["file"]: f for f in catalog["files"]}
    weekly = files["export_sales__weekly__v1.parquet"]
    assert weekly["release_url"].endswith(
        "/releases/download/data-2024-05/export_sales__weekly__v1.parquet"
    )
    assert weekly["site_url"] == "data/downloads/export_sales__weekly__v1.parquet"
    assert (web / "downloads" / "export_sales__weekly__v1.parquet").exists()
    assert files["wasde_full.parquet"]["legacy_alias_of"] == "wasde__values__v1.parquet"
    assert catalog["reports"]["export_sales"]["latest_release_key"] == "2025-09-11"
    assert (web / "datapackage.json").exists()


def test_datapackage_is_valid_frictionless(built: Settings):
    """The descriptor loads under its tabular-data-package profile and every CSV resource
    validates against its Table Schema (Parquet needs a plugin, so only its descriptor)."""
    frictionless = pytest.importorskip("frictionless")
    path = built.publish_dir / "datapackage.json"
    pkg = frictionless.Package(str(path))
    assert pkg.resources and all(r.profile == "tabular-data-resource" for r in pkg.resources)
    csvs = [r for r in pkg.resources if r.format == "csv"]
    assert csvs
    for res in csvs:
        report = res.validate()
        assert report.valid, (res.name, report.flatten(["type", "note"])[:5])


def test_meta_reports_map_extended_without_removing_keys(built: Settings):
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    for key in ("data_release_tag", "next_release", "latest", "history", "downloads"):
        assert key in meta
    esr = meta["reports"]["export_sales"]
    assert {"latest_release_key", "release_ts_utc", "next_release", "rows"} <= set(esr)
    assert esr["latest_release_key"] == "2025-09-11"
    assert esr["release_ts_utc"] == "2025-09-11T12:30:00Z"
    assert esr["next_release"] == "2025-09-18"
    assets = [p.name for p in built.publish_dir.iterdir()] + ["manifest.json"]
    assert release_contract_problems("data-2024-05", meta, assets) == []
