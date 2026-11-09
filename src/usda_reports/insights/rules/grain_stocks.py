"""Grain Stocks insights G1–G3 (plan §6). U.S. corn, soybeans and all wheat; history from the
2010-06-30 release (first ESMIS file in the regular layout).

* G1 stocks_vs_wasde: only for the stock dates that match a WASDE ending stock (corn/soybeans
  September 1, wheat June 1). surprise = NASS total (first print) − the old-crop ending stocks
  in the WASDE public at the release (``fct_stocks_vs_wasde``), in million bushels and %,
  ranked by |surprise %| among every such date since 2010 ("k of n"; percentile only n ≥ 10).
* G2 implied_disappearance: stocks_{q−1} + production_q − stocks_q (``fct_stocks_disappearance``;
  production = WASDE as of the release, harvest quarter only), vs the same quarter of the 5
  prior marketing years. Caveats: imports omitted (small for corn/soybeans); NASS may revise
  production the same day (Small Grains Summary / annual Crop Production) while this uses the
  WASDE figure public at the release.
* G3 on_farm_share: on_farm / total and total_t / total_{t−4q} − 1, vs the same quarter of the
  5 prior years.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from usda_reports.insights import stats
from usda_reports.insights.rules.common import day, num, range_params, rnd, text, ts
from usda_reports.insights.schema import InputRef, Insight

REPORT_ID = "grain_stocks"
COMMODITIES = ("corn", "soybeans", "wheat")
HISTORY_START = "2010-06-30"
SHARE_DP = 6


def to_mbu(kbu: Any) -> float | None:
    """Thousand bushels → million bushels (3 decimals), None stays None."""
    v = num(kbu)
    return None if v is None else round(v / 1000, 3)


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "select count(*) from information_schema.tables where table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def latest_release_key(con: duckdb.DuckDBPyConnection) -> str | None:
    row = con.execute(
        "select max(release_key) from dim_release where report_id = 'grain_stocks'"
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _inputs(release_key: Any, wasde_key: Any = None) -> list[InputRef]:
    refs = [InputRef(report_id=REPORT_ID, release_key=str(release_key))]
    if isinstance(wasde_key, str):
        refs.append(InputRef(report_id="wasde", release_key=wasde_key))
    return refs


def g1_stocks_vs_wasde(con: duckdb.DuckDBPyConnection, latest_key: str | None) -> list[Insight]:
    df = con.execute("select * from fct_stocks_vs_wasde order by commodity_id, as_of_date").df()
    out = []
    for cid in COMMODITIES:
        g = df[df.commodity_id == cid]
        if g.empty:
            continue
        cur = g.iloc[-1]
        ranked = g[g.surprise_pct.notna()]
        pct = num(cur.surprise_pct)
        others = [abs(float(v)) for v in ranked[ranked.as_of_date != cur.as_of_date].surprise_pct]
        n = len(others) + (1 if pct is not None else 0)
        k = stats.rank_high_first(abs(pct), others)[0] if pct is not None else None
        params: dict[str, Any] = {
            "as_of_date": day(cur.as_of_date),
            "market_year": cur.market_year,
            "release_key": cur.release_key,
            "is_latest_release": cur.release_key == latest_key,
            "unit_id": "m_bu",
            "nass_total_mbu": rnd(num(cur.nass_total_mbu), 3),
            "wasde_release_key": text(cur.wasde_release_key),
            "wasde_flag": text(cur.wasde_proj_est_flag),
            "wasde_ending_stocks_mbu": num(cur.wasde_ending_stocks_mbu),
            "surprise_mbu": rnd(num(cur.surprise_mbu), 3),
            "surprise_pct": rnd(pct, SHARE_DP),
            "direction": None
            if pct is None
            else ("above" if pct > 0 else "below" if pct < 0 else "equal"),
            "k": k,
            "order": "largest_abs_first",
            "rank_basis": "abs_surprise_pct",
            "percentile_larger_than": stats.percentile(k, n) if k is not None else None,
            "first_market_year": ranked.market_year.iloc[0] if len(ranked) else None,
            "history_start": HISTORY_START,
            "history": [
                {
                    "market_year": r.market_year,
                    "as_of_date": day(r.as_of_date),
                    "surprise_mbu": round(float(r.surprise_mbu), 3),
                    "surprise_pct": round(float(r.surprise_pct), SHARE_DP),
                    "wasde_release_key": r.wasde_release_key,
                }
                for r in ranked.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"G1:{cid}",
                rule="G1",
                report_id=REPORT_ID,
                commodity_id=cid,
                kind="stocks_vs_wasde",
                params=params,
                n=n,
                window="ending_stock_dates_since_2010",
                robustness="robust",
                caveats=["history_point_in_time", "grain_stocks_first_print"],
                inputs=_inputs(cur.release_key, cur.wasde_release_key),
                as_of=ts(cur.release_ts_utc),
                suppressed_reason="asof_missing" if pct is None else None,
            )
        )
    return out


def g2_implied_disappearance(
    con: duckdb.DuckDBPyConnection, latest_key: str | None
) -> list[Insight]:
    df = con.execute(
        "select * from fct_stocks_disappearance order by commodity_id, as_of_date"
    ).df()
    out = []
    for cid in COMMODITIES:
        g = df[df.commodity_id == cid]
        if g.empty:
            continue
        cur = g.iloc[-1]
        hist = g[
            (g.quarter_of_my == cur.quarter_of_my)
            & (g.my_start >= cur.my_start - 5)
            & (g.my_start <= cur.my_start - 1)
            & g.implied_disappearance_kbu.notna()
        ]
        value = num(cur.implied_disappearance_kbu)
        vals = [float(v) / 1000 for v in hist.implied_disappearance_kbu]
        harvest = bool(cur.is_harvest_quarter)
        reason: Any = None
        if harvest and num(cur.wasde_production_mbu) is None:
            reason = "asof_missing"
        elif value is None:
            reason = "no_data"
        mbu = value / 1000 if value is not None else None
        params: dict[str, Any] = {
            "as_of_date": day(cur.as_of_date),
            "prev_as_of_date": day(cur.prev_as_of_date),
            "market_year": cur.market_year,
            "quarter_of_my": int(cur.quarter_of_my),
            "release_key": cur.release_key,
            "is_latest_release": cur.release_key == latest_key,
            "unit_id": "m_bu",
            "is_harvest_quarter": harvest,
            "prev_stocks_mbu": to_mbu(cur.prev_stocks_kbu),
            "stocks_mbu": to_mbu(cur.stocks_kbu),
            "production_mbu": to_mbu(cur.production_kbu),
            "wasde_release_key": text(cur.wasde_release_key),
            "implied_disappearance_mbu": rnd(mbu, 3),
            **range_params(mbu, vals, 3),
            "history": [
                {
                    "market_year": r.market_year,
                    "as_of_date": day(r.as_of_date),
                    "implied_disappearance_mbu": round(
                        float(r.implied_disappearance_kbu) / 1000, 3
                    ),
                }
                for r in hist.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"G2:{cid}",
                rule="G2",
                report_id=REPORT_ID,
                commodity_id=cid,
                kind="implied_disappearance",
                params=params,
                n=len(vals),
                window="prior_5_my_same_quarter",
                robustness="robust",
                caveats=[
                    "imports_omitted_small_for_corn_soy",
                    "nass_may_revise_production_same_day",
                ],
                inputs=_inputs(cur.release_key, cur.wasde_release_key if harvest else None),
                as_of=ts(cur.release_ts_utc),
                suppressed_reason=reason,
            )
        )
    return out


def g3_on_farm_share(con: duckdb.DuckDBPyConnection, latest_key: str | None) -> list[Insight]:
    df = con.execute(
        "select * from fct_grain_stocks_quarterly order by commodity_id, as_of_date"
    ).df()
    out = []
    for cid in COMMODITIES:
        g = df[df.commodity_id == cid]
        if g.empty:
            continue
        cur = g.iloc[-1]
        cur_date = pd.Timestamp(cur.as_of_date)
        dates = pd.to_datetime(g.as_of_date)
        hist = g[
            (dates.dt.month == cur_date.month)
            & (dates.dt.year >= cur_date.year - 5)
            & (dates.dt.year <= cur_date.year - 1)
            & g.on_farm_share.notna()
        ]
        share = num(cur.on_farm_share)
        vals = [float(v) for v in hist.on_farm_share]
        prev = g[dates == cur_date - pd.DateOffset(years=1)]
        params: dict[str, Any] = {
            "as_of_date": day(cur.as_of_date),
            "market_year": cur.market_year,
            "quarter_of_my": int(cur.quarter_of_my),
            "release_key": cur.first_release_key,
            "is_latest_release": cur.first_release_key == latest_key,
            "unit_id": "m_bu",
            "on_farm_mbu": to_mbu(cur.on_farm_kbu),
            "off_farm_mbu": to_mbu(cur.off_farm_kbu),
            "total_mbu": to_mbu(cur.total_kbu),
            "total_mt": rnd(num(cur.total_mt), 0),
            "on_farm_share": rnd(share, SHARE_DP),
            "total_prev_year_mbu": rnd(float(prev.total_kbu.iloc[0]) / 1000, 3)
            if len(prev)
            else None,
            "total_yoy_pct": rnd(num(cur.total_yoy_pct), SHARE_DP),
            **range_params(share, vals, SHARE_DP),
            "history": [
                {
                    "as_of_date": day(r.as_of_date),
                    "on_farm_share": round(float(r.on_farm_share), SHARE_DP),
                }
                for r in hist.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"G3:{cid}",
                rule="G3",
                report_id=REPORT_ID,
                commodity_id=cid,
                kind="on_farm_share",
                params=params,
                n=len(vals),
                window="prior_5_years_same_stock_date",
                robustness="robust",
                caveats=["nass_revises_previous_quarter"],
                inputs=_inputs(cur.first_release_key),
                as_of=ts(cur.first_release_ts_utc),
                suppressed_reason=None if share is not None else "no_data",
            )
        )
    return out


def all_rules(con: duckdb.DuckDBPyConnection) -> tuple[list[Insight], dict[str, int]]:
    if not _table_exists(con, "fct_grain_stocks_quarterly"):
        return [], {}
    latest = latest_release_key(con)
    if latest is None:
        return [], {}
    g1 = g1_stocks_vs_wasde(con, latest)
    g2 = g2_implied_disappearance(con, latest)
    g3 = g3_on_farm_share(con, latest)
    return g1 + g2 + g3, {"G1": len(g1), "G2": len(g2), "G3": len(g3)}
