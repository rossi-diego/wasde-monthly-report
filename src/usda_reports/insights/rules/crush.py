"""NASS crush insights F1–F3 (plan §6). Soybeans; marketing year September–August; history
window 2015/16+ (ESMIS has NASS files from the 2015-10-01 release only, so no "since 2010"
claims). Every row of ``fct_crush_pace`` is point in time: the NASS vintages and the WASDE that
were public when NASS first printed that month. History = the same month of the 5 prior MYs,
each against its own as-of WASDE.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from usda_reports.insights import stats
from usda_reports.insights.schema import InputRef, Insight

WINDOW_5Y = "prior_5_my_same_month"
HISTORY_START = "2015-10"  # first ESMIS Fats & Oils file; MY 2015/16 is the first full year
COMMODITY = "soybeans"


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def _ts(v: Any) -> str | None:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _s(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def pace_frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("select * from fct_crush_pace order by month").df()


def current_row(pace: pd.DataFrame) -> pd.Series:
    return pace.sort_values("month").iloc[-1]


def history_at_month(pace: pd.DataFrame, cur: pd.Series) -> pd.DataFrame:
    """The same month_of_my in the 5 previous marketing years."""
    h = pace[
        (pace.month_of_my == cur.month_of_my)
        & (pace.my_start >= cur.my_start - 5)
        & (pace.my_start <= cur.my_start - 1)
    ]
    return h.sort_values("my_start")


def _common(cur: pd.Series) -> dict[str, Any]:
    return {
        "market_year": cur.market_year,
        "month": str(pd.Timestamp(cur.month).date()),
        "month_of_my": int(cur.month_of_my),
        "release_key": cur.release_key,
        "first_printed_as": _s(cur.first_printed_as),
        "history_start": HISTORY_START,
    }


def _inputs(cur: pd.Series, wasde_key: Any) -> list[InputRef]:
    refs = [InputRef(report_id="oilseed_crush", release_key=str(cur.release_key))]
    if isinstance(wasde_key, str):
        refs.append(InputRef(report_id="wasde", release_key=wasde_key))
    return refs


def _range(value: float | None, vals: list[float], nd: int) -> dict[str, Any]:
    out: dict[str, Any] = {
        "hist_mean": None,
        "hist_min": None,
        "hist_max": None,
        "position": None,
        "outside_distance": None,
    }
    if not vals:
        return out
    lo, hi = min(vals), max(vals)
    out.update(hist_mean=_r(stats.mean(vals), nd), hist_min=_r(lo, nd), hist_max=_r(hi, nd))
    if value is not None:
        out["position"] = stats.range_position(value, lo, hi)
        out["outside_distance"] = round(stats.outside_distance(value, lo, hi), 4)
    return out


def f1_crush_pace(pace: pd.DataFrame) -> list[Insight]:
    """F1: MY-to-date crush (bu) ÷ the as-of WASDE crush, vs the 5 prior MYs at the same month."""
    if pace.empty:
        return []
    cur = current_row(pace)
    hist = history_at_month(pace, cur)
    hist = hist[hist.pct_of_target.notna()]
    pct = _f(cur.pct_of_target)
    vals = [float(v) for v in hist.pct_of_target]
    params: dict[str, Any] = {
        **_common(cur),
        "unit_id": "bu",
        "cum_bu": _f(cur.cum_bu),
        "cum_st": _f(cur.cum_st),
        "month_crushed_bu": _f(cur.month_crushed_bu),
        "month_crushed_st": _f(cur.month_crushed_st),
        "wasde_release_key": _s(cur.wasde_release_key),
        "target_bu": _f(cur.wasde_crush_bu),
        "target_native": _f(cur.wasde_crush_native),
        "target_unit_id": _s(cur.wasde_crush_unit_id),
        "target_flag": _s(cur.wasde_proj_est_flag),
        "pct": _r(pct, 4),
        **_range(pct, vals, 4),
        "history": [
            {
                "market_year": r.market_year,
                "pct": round(float(r.pct_of_target), 4),
                "wasde_release_key": r.wasde_release_key,
            }
            for r in hist.itertuples()
        ],
    }
    return [
        Insight(
            id=f"F1:{COMMODITY}",
            rule="F1",
            report_id="oilseed_crush",
            commodity_id=COMMODITY,
            kind="crush_pace",
            params=params,
            n=len(vals),
            window=WINDOW_5Y,
            robustness="robust",
            caveats=[
                "history_point_in_time",
                "crush_history_from_2015",
                "nass_revises_previous_month",
            ],
            inputs=_inputs(cur, cur.wasde_release_key),
            as_of=_ts(cur.release_ts_utc),
            suppressed_reason="asof_missing" if pct is None else None,
        )
    ]


def f2_required_monthly_crush(pace: pd.DataFrame, min_months: int = 2) -> list[Insight]:
    """F2: (as-of WASDE crush − MY-to-date) / months remaining vs the mean of the same remaining
    months last MY (as known at the time)."""
    if pace.empty:
        return []
    cur = current_row(pace)
    target = _f(cur.wasde_crush_bu)
    req = _f(cur.required_monthly_bu)
    last = _f(cur.last_my_remaining_mean_bu)
    months = int(cur.months_remaining)
    reason: Any = None
    if target is None:
        reason = "asof_missing"
    elif months < min_months:
        reason = "months_remaining_below_min"
    elif last is None:
        reason = "no_data"
    cum = _f(cur.cum_bu)
    return [
        Insight(
            id=f"F2:{COMMODITY}",
            rule="F2",
            report_id="oilseed_crush",
            commodity_id=COMMODITY,
            kind="required_monthly_crush",
            params={
                **_common(cur),
                "unit_id": "bu",
                "cum_bu": cum,
                "wasde_release_key": _s(cur.wasde_release_key),
                "target_bu": target,
                "target_native": _f(cur.wasde_crush_native),
                "target_unit_id": _s(cur.wasde_crush_unit_id),
                "remaining_to_target_bu": target - cum
                if target is not None and cum is not None
                else None,
                "months_remaining": months,
                "required_monthly_bu": _r(req, 0),
                "last_my_remaining_mean_bu": _r(last, 0),
                "last_my_remaining_n": int(cur.last_my_remaining_n),
                "ratio_required_to_last_my": round(req / last, 4)
                if req is not None and last not in (None, 0)
                else None,
            },
            n=int(cur.last_my_remaining_n),
            window="last_my_same_remaining_months",
            robustness="robust",
            caveats=["nass_revises_previous_month"],
            inputs=_inputs(cur, cur.wasde_release_key),
            as_of=_ts(cur.release_ts_utc),
            suppressed_reason=reason,
        )
    ]


def f3_oil_yield(pace: pd.DataFrame) -> list[Insight]:
    """F3: crude oil lb per bushel crushed in the newest month vs the same month of the 5 prior
    years and vs the WASDE-implied yield (soybean oil production ÷ crush, as of the release)."""
    if pace.empty:
        return []
    cur = current_row(pace)
    hist = history_at_month(pace, cur)
    hist = hist[hist.oil_yield_lb_bu.notna()]
    y = _f(cur.oil_yield_lb_bu)
    vals = [float(v) for v in hist.oil_yield_lb_bu]
    implied = _f(cur.wasde_implied_oil_yield_lb_bu)
    params: dict[str, Any] = {
        **_common(cur),
        "unit_id": "lb_per_bu",
        "oil_yield_lb_bu": _r(y, 4),
        "month_oil_klb": _f(cur.month_oil_klb),
        "month_crushed_bu": _f(cur.month_crushed_bu),
        **_range(y, vals, 4),
        "wasde_oil_release_key": _s(cur.wasde_oil_release_key),
        "wasde_implied_yield_lb_bu": _r(implied, 4),
        "diff_vs_wasde_lb_bu": _r(y - implied, 4)
        if y is not None and implied is not None
        else None,
        "history": [
            {"market_year": r.market_year, "oil_yield_lb_bu": round(float(r.oil_yield_lb_bu), 4)}
            for r in hist.itertuples()
        ],
    }
    return [
        Insight(
            id=f"F3:{COMMODITY}",
            rule="F3",
            report_id="oilseed_crush",
            commodity_id=COMMODITY,
            kind="oil_yield",
            params=params,
            n=len(vals),
            window=WINDOW_5Y,
            robustness="robust",
            caveats=["crush_history_from_2015", "wasde_oil_year_oct_sep"],
            inputs=_inputs(cur, cur.wasde_oil_release_key),
            as_of=_ts(cur.release_ts_utc),
            suppressed_reason="no_data" if y is None else None,
        )
    ]
