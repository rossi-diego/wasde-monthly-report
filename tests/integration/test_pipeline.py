"""End-to-end on a mini dataset: silver → dbt gold → publish (JSON, Excel, Parquet).

Two reports are built from the trimmed 2024-05 CSV fixture: an "April" copy and the real
May file, with U.S. corn ending stocks moved so that drivers and highlights have a revision
to explain. Only U.S./World corn exist, which also checks that publishing degrades
gracefully when a focus commodity has no data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from wasde.config import PROJECT_ROOT, Settings
from wasde.gold import run_dbt
from wasde.manifest import Manifest
from wasde.publish.run import publish_all
from wasde.silver.harmonize import SILVER_COLUMNS, Vocabulary, harmonize
from wasde.silver.parse_csv import parse_csv

pytest.importorskip("dbt")


@pytest.fixture(scope="module")
def built(tmp_path_factory, request) -> Settings:
    root = tmp_path_factory.mktemp("wasde")
    fixtures = Path(request.config.rootpath) / "tests" / "fixtures"
    settings = Settings(
        data_dir=root / "data", web_data_dir=root / "web", config_dir=PROJECT_ROOT / "config"
    )

    may = parse_csv(fixtures / "wasde_2024-05.csv", "2024-05")
    april = may.copy()
    april["report_month"] = "2024-04"
    april["wasde_number"] = 647
    corn_es = (
        (april.report_title.str.startswith("U.S. Feed"))
        & (april.commodity == "Corn")
        & (april.attribute == "Ending Stocks")
    )
    corn_prod = (
        (april.report_title.str.startswith("U.S. Feed"))
        & (april.commodity == "Corn")
        & (april.attribute == "Production")
    )
    april.loc[corn_es, "value"] += 100  # May "cut" ending stocks by 100 ...
    april.loc[corn_prod, "value"] += 100  # ... explained entirely by production
    raw = pd.concat([april, may], ignore_index=True)
    silver, _ = harmonize(raw, Vocabulary.load(settings.config_dir / "mappings.yaml"))
    settings.silver_dir.mkdir(parents=True)
    silver[SILVER_COLUMNS].to_parquet(settings.silver_dir / "wasde.parquet", index=False)

    assert run_dbt(settings, command="run") == 0
    publish_all(settings, Manifest(), tag="data-2024-05")
    return settings


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


def test_excel_latest_report_layout(built: Settings):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(built.publish_dir / "wasde_2024-05_latest.xlsx", read_only=True)
    assert wb.sheetnames[:2] == ["README", "Changes"]
    assert "Corn US" in wb.sheetnames and "All data (long)" in wb.sheetnames


def teardown_module() -> None:
    shutil.rmtree(PROJECT_ROOT / "data" / "gold" / "dbt_target" / "_pytest", ignore_errors=True)
