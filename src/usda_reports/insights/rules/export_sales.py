"""Export Sales insights E1–E3 (plan §6). Metric tons; current marketing year only; next-MY
sales are never added. History = the 5 previous marketing years at the same week_of_my, each
against the WASDE that was public at that time (``fct_export_pace``)."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from usda_reports.insights import stats
from usda_reports.insights.schema import InputRef, Insight

COMMODITIES = ("soybeans", "corn", "wheat", "soybean_meal", "soybean_oil")
WINDOW_5Y = "prior_5_my_same_week"


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _ts(v: Any) -> str | None:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def pace_frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("select * from fct_export_pace order by commodity_id, week_ending").df()


def current_rows(pace: pd.DataFrame) -> dict[str, pd.Series]:
    """Newest week of the newest marketing year per commodity."""
    out: dict[str, pd.Series] = {}
    for cid, g in pace.groupby("commodity_id"):
        g = g[g.esr_market_year == g.esr_market_year.max()]
        out[str(cid)] = g.sort_values("week_ending").iloc[-1]
    return out


def history_at_week(pace: pd.DataFrame, cur: pd.Series) -> pd.DataFrame:
    """The same week_of_my in the 5 previous marketing years."""
    h = pace[
        (pace.commodity_id == cur.commodity_id)
        & (pace.week_of_my == cur.week_of_my)
        & (pace.esr_market_year >= cur.esr_market_year - 5)
        & (pace.esr_market_year <= cur.esr_market_year - 1)
    ]
    return h.sort_values("esr_market_year")


def _inputs(cur: pd.Series, with_wasde: bool) -> list[InputRef]:
    refs = [InputRef(report_id="export_sales", release_key=str(cur.release_key))]
    if with_wasde and isinstance(cur.wasde_release_key, str):
        refs.append(InputRef(report_id="wasde", release_key=cur.wasde_release_key))
    return refs


def _common(cur: pd.Series) -> dict[str, Any]:
    return {
        "market_year": cur.market_year,
        "esr_market_year": int(cur.esr_market_year),
        "week_ending": str(pd.Timestamp(cur.week_ending).date()),
        "week_of_my": int(cur.week_of_my),
        "release_key": cur.release_key,
        "unit_id": "mt",
    }


def _target(cur: pd.Series) -> dict[str, Any]:
    return {
        "wasde_release_key": cur.wasde_release_key
        if isinstance(cur.wasde_release_key, str)
        else None,
        "target_mt": _f(cur.wasde_exports_mt),
        "target_native": _f(cur.wasde_exports_native),
        "target_unit_id": cur.wasde_unit_id if isinstance(cur.wasde_unit_id, str) else None,
        "target_flag": cur.wasde_proj_est_flag
        if isinstance(cur.wasde_proj_est_flag, str)
        else None,
    }


def e1_commitment_pace(pace: pd.DataFrame) -> list[Insight]:
    """E1: (accumulated + outstanding) / as-of WASDE exports vs the 5 prior MYs at the same w."""
    out = []
    for cid, cur in sorted(current_rows(pace).items(), key=lambda kv: COMMODITIES.index(kv[0])):
        hist = history_at_week(pace, cur)
        hist = hist[hist.pct_of_target.notna()]
        pct = _f(cur.pct_of_target)
        vals = [float(v) for v in hist.pct_of_target]
        lo, hi, mu = (min(vals), max(vals), stats.mean(vals)) if vals else (None, None, None)
        params: dict[str, Any] = {
            **_common(cur),
            **_target(cur),
            "total_commitment_mt": _f(cur.total_commitment_mt),
            "accumulated_exports_mt": _f(cur.accumulated_exports_mt),
            "outstanding_sales_mt": _f(cur.outstanding_sales_mt),
            "pct": round(pct, 4) if pct is not None else None,
            "hist_mean": round(mu, 4) if mu is not None else None,
            "hist_min": round(lo, 4) if lo is not None else None,
            "hist_max": round(hi, 4) if hi is not None else None,
            "position": stats.range_position(pct, lo, hi)
            if pct is not None and lo is not None and hi is not None
            else None,
            "outside_distance": round(stats.outside_distance(pct, lo, hi), 4)
            if pct is not None and lo is not None and hi is not None
            else None,
            "history": [
                {
                    "market_year": r.market_year,
                    "pct": round(float(r.pct_of_target), 4),
                    "wasde_release_key": r.wasde_release_key,
                }
                for r in hist.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"E1:{cid}",
                rule="E1",
                report_id="cross",
                commodity_id=cid,
                kind="commitment_pace",
                params=params,
                n=len(vals),
                window=WINDOW_5Y,
                robustness="robust",
                caveats=["esr_not_census", "history_point_in_time", "latest_only_history"],
                inputs=_inputs(cur, True),
                as_of=_ts(cur.release_ts_utc),
                suppressed_reason="asof_missing" if pct is None else None,
            )
        )
    return out


def e2_required_weekly_sales(pace: pd.DataFrame, min_weeks: int = 6) -> list[Insight]:
    """E2: (target − accumulated − outstanding) / weeks_remaining vs the 4-week mean net sales."""
    out = []
    for cid, cur in sorted(current_rows(pace).items(), key=lambda kv: COMMODITIES.index(kv[0])):
        req = _f(cur.required_weekly_sales_mt)
        target = _f(cur.wasde_exports_mt)
        avg4 = _f(cur.net_sales_4wk_avg_mt)
        weeks = int(cur.weeks_remaining)
        reason: Any = None
        if target is None:
            reason = "asof_missing"
        elif weeks < min_weeks:
            reason = "weeks_remaining_below_min"
        elif avg4 is None:
            reason = "no_data"
        out.append(
            Insight(
                id=f"E2:{cid}",
                rule="E2",
                report_id="cross",
                commodity_id=cid,
                kind="required_weekly_sales",
                params={
                    **_common(cur),
                    **_target(cur),
                    "total_commitment_mt": _f(cur.total_commitment_mt),
                    "remaining_to_target_mt": (
                        target - float(cur.total_commitment_mt) if target is not None else None
                    ),
                    "weeks_remaining": weeks,
                    "required_weekly_mt": round(req, 1) if req is not None else None,
                    "net_sales_4wk_avg_mt": round(avg4, 1) if avg4 is not None else None,
                    "ratio_required_to_avg": round(req / avg4, 3)
                    if req is not None and avg4 not in (None, 0)
                    else None,
                },
                n=4 if avg4 is not None else 0,
                window="last_4_weeks",
                robustness="robust",
                caveats=["esr_not_census"],
                inputs=_inputs(cur, True),
                as_of=_ts(cur.release_ts_utc),
                suppressed_reason=reason,
            )
        )
    return out


def e3_china_share_soy(pace: pd.DataFrame) -> list[Insight]:
    """E3: China's share of soybean commitments (and the unknown-destinations share) vs the 5
    prior MYs at the same week."""
    rows = current_rows(pace)
    if "soybeans" not in rows:
        return []
    cur = rows["soybeans"]
    total = float(cur.total_commitment_mt)
    hist = history_at_week(pace, cur)
    hist = hist[hist.total_commitment_mt > 0]
    shares = [
        float(r.china_commitment_mt) / float(r.total_commitment_mt) for r in hist.itertuples()
    ]
    china = float(cur.china_commitment_mt) / total if total > 0 else None
    unknown = float(cur.unknown_commitment_mt) / total if total > 0 else None
    lo, hi = (min(shares), max(shares)) if shares else (None, None)
    return [
        Insight(
            id="E3:soybeans",
            rule="E3",
            report_id="export_sales",
            commodity_id="soybeans",
            kind="china_share_soy",
            params={
                **_common(cur),
                "total_commitment_mt": total,
                "china_commitment_mt": float(cur.china_commitment_mt),
                "unknown_commitment_mt": float(cur.unknown_commitment_mt),
                "china_share": round(china, 4) if china is not None else None,
                "unknown_share": round(unknown, 4) if unknown is not None else None,
                "hist_mean": round(stats.mean(shares) or 0, 4) if shares else None,
                "hist_min": round(lo, 4) if lo is not None else None,
                "hist_max": round(hi, 4) if hi is not None else None,
                "position": stats.range_position(china, lo, hi)
                if china is not None and lo is not None and hi is not None
                else None,
                "history": [
                    {
                        "market_year": r.market_year,
                        "china_share": round(
                            float(r.china_commitment_mt) / float(r.total_commitment_mt), 4
                        ),
                        "unknown_share": round(
                            float(r.unknown_commitment_mt) / float(r.total_commitment_mt), 4
                        ),
                    }
                    for r in hist.itertuples()
                ],
            },
            n=len(shares),
            window=WINDOW_5Y,
            robustness="robust",
            caveats=["unknown_may_hide_china", "latest_only_history"],
            inputs=_inputs(cur, False),
            as_of=_ts(cur.release_ts_utc),
            suppressed_reason="no_data" if china is None else None,
        )
    ]
