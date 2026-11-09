"""End-to-end on a mini dataset: silver → dbt gold → publish (JSON, Excel, Parquet).

The mini build itself is the session fixture ``built`` in ``conftest.py``.
"""

from __future__ import annotations

import json
import shutil

import duckdb
import pandas as pd
import pytest

from usda_reports.core.config import PROJECT_ROOT, Settings

pytest.importorskip("dbt")


def test_gold_drivers_explain_the_revision(built: Settings):
    con = duckdb.connect(str(built.duckdb_path))
    row = con.execute(
        """select d_ending_stocks, d_production, d_other from fct_ending_stocks_drivers
           where table_id='us_feed_grains_corn' and commodity_id='corn' and market_year='2024/25'"""
    ).fetchone()
    assert row == (-100, -100, 0)
    su = con.execute(
        "select stocks_to_use_pct from fct_balance_sheet where report_month='2024-05' and table_id='us_feed_grains_corn' and market_year='2024/25'"
    ).fetchone()[0]
    assert 10 < su < 20
    seq = con.execute("select list(report_seq order by report_month) from dim_reports").fetchone()[
        0
    ]
    assert seq == [1, 2]


def test_publish_outputs(built: Settings):
    web = built.web_data_dir
    meta = json.loads((web / "meta.json").read_text(encoding="utf-8"))
    assert meta["latest"]["report_month"] == "2024-05"
    assert meta["data_release_tag"] == "data-2024-05"
    files = {d["file"] for d in meta["downloads"]}
    assert {"wasde_2024-05_latest.xlsx", "wasde_full.parquet", "wasde_full.csv.gz"} <= files
    for f in files:
        assert (web / "downloads" / f).stat().st_size > 0

    overview = json.loads((web / "overview.json").read_text(encoding="utf-8"))
    top = overview["highlights"][0]
    assert (
        top["commodity"] == "corn" and top["attribute"] == "ending_stocks" and top["delta"] == -100
    )
    assert "Effect on stocks: production −100 mil. bu" in top["sentence"]

    corn = json.loads(
        (web / "commodities" / "corn" / "united_states.json").read_text(encoding="utf-8")
    )
    assert [c["market_year"] for c in corn["balance_sheet"]["columns"]][-1] == "2024/25"
    assert corn["revisions"]["ending_stocks"]

    catalog = json.loads((web / "catalog.json").read_text(encoding="utf-8"))
    assert {c["id"] for c in catalog} == {"us_feed_grains_corn", "world_corn"}
    full = pd.read_parquet(web / "downloads" / "wasde_full.parquet")
    assert full.report_month.nunique() == 2

    # Multi-report meta map + versioned catalogue with a byte-identical legacy alias.
    assert meta["reports"]["wasde"]["latest_release_key"] == "2024-05"
    assert meta["reports"]["wasde"]["release_ts_utc"] == "2024-05-10T16:00:00Z"
    pub = built.publish_dir
    for name in ("values", "balance_sheets", "revisions", "changes"):
        assert (pub / f"wasde__{name}__v1.parquet").stat().st_size > 0
    alias = (pub / "wasde_full.parquet").read_bytes()
    assert alias == (pub / "wasde__values__v1.parquet").read_bytes()
    assert alias == (web / "downloads" / "wasde_full.parquet").read_bytes()
    datasets = json.loads((pub / "datasets.json").read_text(encoding="utf-8"))
    alias_entry = next(d for d in datasets if d["file"] == "wasde_full.parquet")
    assert alias_entry["legacy_alias_of"] == "wasde__values__v1.parquet"
    assert alias_entry["rows"] == len(full)


def test_excel_latest_report_layout(built: Settings):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(built.publish_dir / "wasde_2024-05_latest.xlsx", read_only=True)
    assert wb.sheetnames[:2] == ["README", "Changes"]
    assert "Corn US" in wb.sheetnames and "All data (long)" in wb.sheetnames


def teardown_module() -> None:
    shutil.rmtree(PROJECT_ROOT / "data" / "gold" / "dbt_target" / "_pytest", ignore_errors=True)
