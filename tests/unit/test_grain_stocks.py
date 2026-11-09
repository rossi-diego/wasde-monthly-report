"""NASS Grain Stocks: parser (table 1, both title layouts, "1-Mar" labels), marketing years,
ingest (duplicate ESMIS listings, notices), insights G1–G3 and the home card. Fixtures are
real ESMIS zips (trimmed to grst_all_tables.csv) and slices of the gold marts recorded from
the 2026-11-09 local run (no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import httpx
import pandas as pd
import pytest
import respx

from usda_reports.bronze.store import BronzeStore
from usda_reports.core.config import PROJECT_ROOT
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.manifest import Manifest
from usda_reports.insights import gates as gates_mod
from usda_reports.insights.engine import release_index
from usda_reports.insights.hero import grain_stocks_card
from usda_reports.insights.rules import grain_stocks as gs
from usda_reports.insights.schema import Gates
from usda_reports.nass_common.ingest import ingest_zips
from usda_reports.nass_common.spec import StoredRelease
from usda_reports.reports.grain_stocks.parse import (
    MY_START_MONTH,
    build_frame,
    market_year,
    parse_release,
    validate,
)
from usda_reports.reports.grain_stocks.source import GrainStocksError, SourceConfig

FX = Path(__file__).resolve().parents[1] / "fixtures" / "grain_stocks"
URL = "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/GraiStoc"
NOW = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)


@pytest.fixture
def cfg(config_dir: Path) -> SourceConfig:
    return SourceConfig.load(config_dir / "reports" / "grain_stocks" / "source.yaml")


def zip_bytes(key: str) -> bytes:
    return (FX / f"{key}.zip").read_bytes()


def rel(key: str) -> StoredRelease:
    return StoredRelease(key=key, sha256="0" * 64, edition=1, url=None, data=zip_bytes(key))


def test_marketing_years_and_quarters():
    assert market_year("corn", date(2026, 9, 1)) == ("2025/26", 2025, 4)  # ending stocks
    assert market_year("corn", date(2026, 12, 1)) == ("2026/27", 2026, 1)  # harvest quarter
    assert market_year("soybeans", date(2027, 3, 1)) == ("2026/27", 2026, 2)
    assert market_year("wheat", date(2026, 6, 1)) == ("2025/26", 2025, 4)
    assert market_year("wheat", date(2026, 9, 1)) == ("2026/27", 2026, 1)
    seed = pd.read_csv(PROJECT_ROOT / "dbt" / "seeds" / "dim_commodity.csv").set_index(
        "commodity_id"
    )
    for cid, month in MY_START_MONTH.items():
        assert seed.loc[cid, "my_start_month"] == month


def test_release_2026_09_30_matches_the_published_text(cfg):
    df = parse_release(zip_bytes("2026-09-30"), cfg)
    cur = df[(df.column_role == "current") & (df.position == "total")].set_index("commodity_id")
    # grst0926_0.txt: corn 2.10 billion, soybeans 315 million, all wheat 1.85 billion bushels.
    assert cur.value.to_dict() == {"corn": 2095057, "soybeans": 315133, "wheat": 1845743}
    assert set(cur.as_of_date) == {date(2026, 9, 1)} and set(df.unit_id) == {"k_bu"}
    on = df[
        (df.commodity_id == "corn") & (df.position == "on_farm") & (df.column_role == "current")
    ]
    assert on.value.iloc[0] == 787300
    # Every printed date of both years is kept (December 1, 2026 is not yet printed).
    corn = df[(df.commodity_id == "corn") & (df.position == "total")]
    assert len(corn) == 7 and date(2026, 12, 1) not in set(corn.as_of_date)


def test_old_title_layout_and_excel_date_labels(cfg):
    old = parse_release(zip_bytes("2010-06-30"), cfg)
    assert old.reported_as_of.iloc[0] == date(2010, 6, 1)
    jan = parse_release(zip_bytes("2013-01-11"), cfg)  # "1-Mar" … "1-Dec" date labels
    assert jan.reported_as_of.iloc[0] == date(2012, 12, 1)
    assert {"corn", "soybeans", "wheat"} == set(jan.commodity_id)


def test_build_frame_envelope_revisions_and_contract(cfg, config_dir):
    silver = build_frame([rel("2026-06-30"), rel("2026-09-30")], cfg)
    contract = Contract.load(config_dir / "contracts" / "grain_stocks.yaml")
    validate(silver, contract)
    ts = silver[silver.release_key == "2026-09-30"].release_ts_utc.iloc[0]
    assert ts.isoformat() == "2026-09-30T16:00:00+00:00"  # 12:00 ET (EDT)
    june = silver[
        (silver.commodity_id == "corn") & (silver.position == "total")
        & (silver.as_of_date == date(2026, 6, 1))
    ].set_index("release_key").value  # fmt: skip
    # June 1 first printed on 2026-06-30, revised on 2026-09-30.
    assert june["2026-06-30"] == 5294828 and june["2026-09-30"] == 5291284
    bad = silver.copy()
    bad.loc[bad.position == "on_farm", "value"] += 10
    with pytest.raises(ContractError):
        validate(bad, contract)
    with pytest.raises(GrainStocksError):  # lag check: September stocks "released" in June
        build_frame([StoredRelease("2026-06-30", "0" * 64, 1, None, zip_bytes("2026-09-30"))], cfg)


@respx.mock
def test_ingest_keeps_highest_esmis_id_and_skips_notices(tmp_path, cfg):
    page = json.loads((FX / "esmis_page0.json").read_text(encoding="utf-8"))
    respx.get(URL, params={"page": "0"}).mock(return_value=httpx.Response(200, json=page))
    best = max((i for i in page["results"] if i["release_datetime"].startswith("2025-09-30")),
               key=lambda i: int(i["id"]))  # fmt: skip
    url = next(f for f in best["files"] if f.endswith(".zip"))
    route = respx.get(url).mock(return_value=httpx.Response(200, content=zip_bytes("2026-09-30")))
    store = BronzeStore(tmp_path, Manifest(), "grain_stocks", "12:00")
    cfg2 = cfg.model_copy(update={"history_start": "2010-06-30"})
    with httpx.Client() as c:
        r = ingest_zips(
            c, store, cfg2, title="Grain Stocks", log_prefix="gs", error=GrainStocksError,
            pause_s=0,
        )  # fmt: skip
    assert r.ingested == ["2025-09-30"] and route.call_count == 1
    assert r.skipped == ["2019-01-11"] and store.entries["2019-01-11"].status == "skipped"


@respx.mock
def test_ingest_retries_a_release_first_listed_without_a_zip(tmp_path, cfg):
    """ESMIS posts the PDF/TXT first and attaches the zip minutes later: the first run
    records the release as skipped, the next run (zip now in files[]) stores it as
    edition 1 instead of ignoring it forever."""
    page = json.loads((FX / "esmis_page0.json").read_text(encoding="utf-8"))
    best = max((i for i in page["results"] if i["release_datetime"].startswith("2025-09-30")),
               key=lambda i: int(i["id"]))  # fmt: skip
    zip_url = next(f for f in best["files"] if f.endswith(".zip"))
    early = {**best, "files": [f for f in best["files"] if not f.endswith(".zip")]}
    one = lambda item: {**page, "results": [item]}  # noqa: E731
    cfg2 = cfg.model_copy(update={"history_start": "2025-09-30"})
    store = BronzeStore(tmp_path, Manifest(), "grain_stocks", "12:00")
    route = respx.get(zip_url).mock(
        return_value=httpx.Response(200, content=zip_bytes("2026-09-30"))
    )
    listing = respx.get(URL, params={"page": "0"})

    def run():
        with httpx.Client() as c:
            return ingest_zips(
                c, store, cfg2, title="Grain Stocks", log_prefix="gs", error=GrainStocksError,
                pause_s=0,
            )  # fmt: skip

    listing.mock(return_value=httpx.Response(200, json=one(early)))
    r = run()
    assert r.skipped == ["2025-09-30"] and r.ingested == [] and route.call_count == 0
    assert store.entries["2025-09-30"].status == "skipped"
    # Same listing again: still no zip, nothing fetched, not re-recorded.
    r = run()
    assert r.skipped == [] and r.ingested == [] and route.call_count == 0
    # The zip is attached: picked up as edition 1.
    listing.mock(return_value=httpx.Response(200, json=one(best)))
    r = run()
    assert r.ingested == ["2025-09-30"] and route.call_count == 1
    e = store.entries["2025-09-30"]
    assert e.status == "ok" and e.edition == 1 and e.url == zip_url


# ------------------------------------------------------------------ insights G1–G3


@pytest.fixture
def con():
    c = duckdb.connect()
    for name in ("fct_grain_stocks_quarterly", "fct_stocks_vs_wasde", "fct_stocks_disappearance"):
        c.execute(
            f"create table {name} as select * from read_parquet('{(FX / name).as_posix()}.parquet')"
        )
    dr = FX.parent / "nass_dim_release.parquet"
    c.execute(f"create table dim_release as select * from read_parquet('{dr.as_posix()}')")
    # The as-of WASDE vintages referenced by the G1/G2 fixture rows (stale by NOW on purpose).
    c.execute(
        """insert into dim_release (report_id, release_key, release_ts_utc)
           select distinct 'wasde', wasde_release_key, wasde_release_ts_utc
           from fct_stocks_vs_wasde where wasde_release_key is not null"""
    )
    yield c
    c.close()


def _gated(con, insights):
    g = Gates(stale_after_days={"grain_stocks": 192, "wasde": 76})
    return {i.id: gates_mod.apply(i, g, NOW, release_index(con)) for i in insights}


def test_g1_surprise_vs_asof_wasde_ranked_since_2010(con):
    ins, n = gs.all_rules(con)
    assert n == {"G1": 3, "G2": 3, "G3": 3}
    g = _gated(con, ins)
    corn = g["G1:corn"]
    p = corn.params
    assert p["as_of_date"] == "2026-09-01" and p["market_year"] == "2025/26"
    assert p["wasde_release_key"] == "2026-09" and p["wasde_ending_stocks_mbu"] == 1922
    assert p["surprise_mbu"] == pytest.approx(2095.057 - 1922)
    assert corn.n == 17 and p["percentile_larger_than"] is not None  # n >= 10
    assert p["order"] == "largest_abs_first" and 1 <= p["k"] <= corn.n
    assert corn.suppressed_reason is None and p["is_latest_release"]
    # Wheat's ending-stock date is June 1: an older release, its as-of WASDE (June) was
    # current at that release, so it is not stale although the WASDE is old by now.
    wheat = g["G1:wheat"]
    assert wheat.params["as_of_date"] == "2026-06-01" and wheat.suppressed_reason is None
    assert not wheat.params["is_latest_release"]
    assert {"history_point_in_time", "grain_stocks_first_print"} <= set(corn.caveats)


def test_g2_identity_and_caveats_g3_share(con):
    g = _gated(con, gs.all_rules(con)[0])
    g2 = g["G2:corn"].params
    # grst0926_0.txt: "June - August 2026 indicated disappearance is 3.20 billion bushels".
    assert g2["implied_disappearance_mbu"] == pytest.approx(5291.284 - 2095.057)
    assert g2["production_mbu"] == 0 and not g2["is_harvest_quarter"]
    assert g["G2:corn"].caveats[:2] == [
        "imports_omitted_small_for_corn_soy",
        "nass_may_revise_production_same_day",
    ]
    assert g["G2:corn"].n == 5 and "small_sample" in g["G2:corn"].caveats
    g3 = g["G3:corn"].params
    assert g3["on_farm_share"] == pytest.approx(787.3 / 2095.057, abs=1e-6)
    assert g3["total_yoy_pct"] == pytest.approx(2095057 / 1551286 - 1, abs=1e-6)


def test_grain_stocks_card_prefers_the_newest_release(con):
    g = _gated(con, gs.all_rules(con)[0])
    card = grain_stocks_card(list(g.values()))
    assert card is not None and card.rule == "G1" and card.params["is_latest_release"]
