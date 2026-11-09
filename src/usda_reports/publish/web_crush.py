"""Site JSON for the crush page: ``web/public/data/reports/oilseed_crush/``.

* ``index.json``: latest release, next release, the commodity file.
* ``soybeans.json``: the newest month's KPIs, the point-in-time USDA (WASDE) crush target, the
  pace of the current MY and the 5 prior MYs (each as % of the USDA projection public at the
  time) with the 5-year band, what is still needed (F2), oil yield by month vs the 5-year band
  and the WASDE-implied yield (F3), and the last 24 months of crush. Every number comes from
  gold; the browser only formats. NOPA is never part of this data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from usda_reports.core.logs import get_logger
from usda_reports.insights import stats
from usda_reports.publish.web_json import _dump

log = get_logger(__name__)

SCHEMA_VERSION = 1
COMMODITY = "soybeans"
HISTORY_START = "2015-10"
MONTHS_SHOWN = 24


def _f(v: Any, nd: int | None = None) -> float | None:
    if v is None or pd.isna(v):
        return None
    return round(float(v), nd) if nd is not None else float(v)


def _ts(v: Any) -> str | None:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _d(v: Any) -> str | None:
    return None if v is None or pd.isna(v) else str(pd.Timestamp(v).date())


def _s(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def _band(pace: pd.DataFrame, col: str, my_start: int, nd: int) -> list[list[Any]]:
    """[month_of_my, mean, min, max, n] of ``col`` over the 5 MYs before ``my_start``."""
    hist = pace[(pace.my_start >= my_start - 5) & (pace.my_start <= my_start - 1)]
    out = []
    for m in range(1, 13):
        vals = [float(v) for v in hist[hist.month_of_my == m][col].dropna()]
        if not vals:
            continue
        out.append([m, _f(stats.mean(vals), nd), _f(min(vals), nd), _f(max(vals), nd), len(vals)])
    return out


def crush_payload(
    con: duckdb.DuckDBPyConnection, next_release: str | None
) -> dict[str, Any] | None:
    pace = con.execute("select * from fct_crush_pace order by month").df()
    monthly = con.execute("select * from fct_soy_crush_monthly order by month").df()
    if pace.empty or monthly.empty:
        return None
    cur = pace.iloc[-1]
    my = int(cur.my_start)
    series = []
    for y in range(my - 5, my + 1):
        g = pace[pace.my_start == y].sort_values("month_of_my")
        if g.empty:
            continue
        series.append(
            {
                "market_year": g.market_year.iloc[0],
                "my_start": y,
                "current": y == my,
                # [month_of_my, pct_of_target (null without an as-of target), wasde_release_key]
                "points": [
                    [int(r.month_of_my), _f(r.pct_of_target, 5), _s(r.wasde_release_key)]
                    for r in g.itertuples()
                ],
                # [month_of_my, oil lb/bu as first printed]
                "yield": [[int(r.month_of_my), _f(r.oil_yield_lb_bu, 4)] for r in g.itertuples()],
            }
        )
    last_my = monthly[
        (monthly.my_start == my - 1) & (monthly.month_of_my > int(cur.month_of_my))
    ].sort_values("month")
    recent = monthly.tail(MONTHS_SHOWN)
    latest_month = monthly.iloc[-1]
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": "oilseed_crush",
        "commodity_id": COMMODITY,
        "label": "Soybeans",
        "history_start": HISTORY_START,
        "market_year": cur.market_year,
        "my_start": my,
        "latest": {
            "release_key": cur.release_key,
            "release_ts_utc": _ts(cur.release_ts_utc),
            "month": _d(cur.month),
            "month_of_my": int(cur.month_of_my),
            "first_printed_as": _s(cur.first_printed_as),
            "vintage_quality": "as_published",
        },
        "next_release": next_release,
        "target": {
            "wasde_release_key": _s(cur.wasde_release_key),
            "wasde_release_ts_utc": _ts(cur.wasde_release_ts_utc),
            "crush_native": _f(cur.wasde_crush_native),
            "crush_bu": _f(cur.wasde_crush_bu),
            "unit_id": _s(cur.wasde_crush_unit_id),
            "flag": _s(cur.wasde_proj_est_flag),
            "oil_release_key": _s(cur.wasde_oil_release_key),
            "oil_production_native": _f(cur.wasde_oil_production_native),
            "oil_unit_id": _s(cur.wasde_oil_unit_id),
            "implied_oil_yield_lb_bu": _f(cur.wasde_implied_oil_yield_lb_bu, 4),
        },
        "kpis": {
            "month_crushed_st": _f(cur.month_crushed_st),
            "month_crushed_bu": _f(cur.month_crushed_bu, 0),
            "month_oil_klb": _f(cur.month_oil_klb),
            "month_meal_st": _f(latest_month.meal_st)
            if pd.Timestamp(latest_month.month) == pd.Timestamp(cur.month)
            else None,
            "oil_yield_lb_bu": _f(cur.oil_yield_lb_bu, 4),
            "cum_bu": _f(cur.cum_bu, 0),
            "cum_st": _f(cur.cum_st),
            "pct_of_target": _f(cur.pct_of_target, 5),
            "n_5yr": int(cur.n_5yr),
            "pct_5yr_mean": _f(cur.pct_5yr_mean, 5),
            "pct_5yr_min": _f(cur.pct_5yr_min, 5),
            "pct_5yr_max": _f(cur.pct_5yr_max, 5),
            "months_remaining": int(cur.months_remaining),
            "required_monthly_bu": _f(cur.required_monthly_bu, 0),
            "last_my_remaining_mean_bu": _f(cur.last_my_remaining_mean_bu, 0),
            "last_my_remaining_n": int(cur.last_my_remaining_n),
            "n_yield_5yr": int(cur.n_yield_5yr),
            "yield_5yr_mean": _f(cur.yield_5yr_mean, 4),
            "yield_5yr_min": _f(cur.yield_5yr_min, 4),
            "yield_5yr_max": _f(cur.yield_5yr_max, 4),
        },
        "pace": {
            # Legend contract: history = % of the USDA projection public at the time.
            "basis": "pct_of_usda_projection_at_the_time",
            "series": series,
            # [month_of_my, mean, min, max, n] of the 5 prior MYs at each month.
            "band": _band(pace, "pct_of_target", my, 5),
        },
        "yield": {
            "unit_id": "lb_per_bu",
            "band": _band(pace, "oil_yield_lb_bu", my, 4),
            "wasde_implied_lb_bu": _f(cur.wasde_implied_oil_yield_lb_bu, 4),
        },
        "remaining": {
            "market_year": f"{my - 1}/{my % 100:02d}",
            # Latest revised values of the remaining months of last MY (bushels).
            "last_my_months": [
                {
                    "month": _d(r.month),
                    "month_of_my": int(r.month_of_my),
                    "crushed_bu": _f(r.crushed_bu, 0),
                }
                for r in last_my.itertuples()
            ],
        },
        "monthly": [
            {
                "month": _d(r.month),
                "market_year": r.market_year,
                "month_of_my": int(r.month_of_my),
                "crushed_st": _f(r.crushed_st),
                "crushed_bu": _f(r.crushed_bu, 0),
                "oil_klb": _f(r.oil_klb),
                "meal_st": _f(r.meal_st),
                "oil_yield_lb_bu": _f(r.oil_yield_lb_bu, 4),
                "is_revised": bool(r.is_revised),
                "latest_release_key": r.latest_release_key,
            }
            for r in recent.itertuples()
        ],
    }


def build_crush(
    con: duckdb.DuckDBPyConnection, out_dir: Path, next_release: str | None
) -> dict[str, Any] | None:
    """Write the crush page JSON; returns the index (None when crush has no data)."""
    exists = con.execute(
        "select count(*) from information_schema.tables where table_name = 'fct_crush_pace'"
    ).fetchone()
    if not exists or not exists[0]:
        return None
    payload = crush_payload(con, next_release)
    if payload is None:
        return None
    folder = out_dir / "reports" / "oilseed_crush"
    _dump(folder / f"{COMMODITY}.json", payload)
    index = {
        "schema_version": SCHEMA_VERSION,
        "report_id": "oilseed_crush",
        "latest": payload["latest"],
        "next_release": next_release,
        "history_start": HISTORY_START,
        "commodities": [
            {
                "id": COMMODITY,
                "label": payload["label"],
                "market_year": payload["market_year"],
                "file": f"reports/oilseed_crush/{COMMODITY}.json",
            }
        ],
    }
    _dump(folder / "index.json", index)
    log.info("publish.oilseed_crush", release=payload["latest"]["release_key"])
    return index
