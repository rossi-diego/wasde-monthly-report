"""WASDE insights W1–W4 (plan §6). Each function returns un-gated :class:`Insight` objects."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from usda_reports.insights import stats
from usda_reports.insights.schema import InputRef, Insight
from usda_reports.publish.focus import Focus

# U.S. balance sheets the rank insights cover (plan §6: corn, soybeans, wheat).
US_SHEETS = {
    "corn": ("us_feed_grains_corn", "corn"),
    "soybeans": ("us_soybeans_products", "soybeans"),
    "wheat": ("us_wheat", "wheat"),
}
HISTORY_FIRST_MY = 2010  # MY 2010/11
W4_EXPORTERS = ("united_states", "brazil", "argentina", "paraguay")
MY_RE = "^[0-9]{4}/[0-9]{2}$"


def _f(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def latest_month(con: duckdb.DuckDBPyConnection) -> tuple[str, str]:
    row = con.execute(
        """select report_month,
                  strftime(min(release_ts_utc) at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ')
           from fct_wasde where is_latest_report group by report_month"""
    ).fetchone()
    assert row is not None
    return str(row[0]), str(row[1])


def _new_crop(con: duckdb.DuckDBPyConnection, month: str, table: str, commodity: str) -> str | None:
    row = con.execute(
        f"""select max(market_year) from fct_balance_sheet
            where report_month = ? and table_id = ? and commodity_id = ?
              and region_id = 'united_states' and regexp_matches(market_year, '{MY_RE}')""",
        [month, table, commodity],
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _base(rule: str, kind: str, commodity: str | None, month: str, ts: str) -> dict[str, Any]:
    return {
        "rule": rule,
        "report_id": "wasde",
        "commodity_id": commodity,
        "kind": kind,
        "inputs": [InputRef(report_id="wasde", release_key=month)],
        "as_of": ts,
    }


def w1_change_vs_prev(
    con: duckdb.DuckDBPyConnection, focus: Focus, month: str, ts: str
) -> tuple[list[Insight], int]:
    """W1: the headline revision (largest |Δ| / median same-month |Δ| above the materiality
    floor) plus each U.S. ending-stocks change used by the hero. Returns (insights, n_screened)."""
    us_pairs = [(c.us.table, c.us.commodity, fid) for fid, c in focus.commodities.items()]
    df = con.execute(
        f"""
        with recent as (
            select table_id, market_year,
                   dense_rank() over (partition by table_id order by market_year desc) as my_rank
            from (select distinct table_id, market_year from fct_changes
                  where report_month = $month and regexp_matches(market_year, '{MY_RE}'))
        )
        select c.table_id, c.commodity_id, c.attribute_id, c.market_year, c.value, c.prev_value,
               c.delta, c.pct_delta, c.unit_id, c.seasonal_score, c.median_abs_delta,
               c.n_history, r.my_rank
        from fct_changes c join recent r using (table_id, market_year)
        where c.report_month = $month and c.region_id = 'united_states'
          and r.my_rank <= 2 and c.months_since_prev = 1
          and c.attribute_id in (select unnest($attrs))
        """,
        {"month": month, "attrs": focus.highlights.attributes},
    ).df()
    pairs = {(t, c): fid for t, c, fid in us_pairs}
    df = df[[(t, c) in pairs for t, c in zip(df.table_id, df.commodity_id, strict=True)]]
    n_screened = len(df)
    floors = [
        focus.highlights.floor("us", c, a)
        for c, a in zip(df.commodity_id, df.attribute_id, strict=True)
    ]
    df = df.assign(floor=floors)
    material = df[
        (df.delta != 0)
        & df.seasonal_score.notna()
        & df.floor.notna()
        & (df.delta.abs() >= df.floor.fillna(0))
    ]
    out: list[Insight] = []

    def params(r: pd.Series, headline: bool) -> dict[str, Any]:
        return {
            "headline": headline,
            "table_id": r.table_id,
            "attribute_id": r.attribute_id,
            "market_year": r.market_year,
            "value": _f(r.value),
            "prev_value": _f(r.prev_value),
            "delta": _f(r.delta),
            "pct_delta": _f(r.pct_delta),
            "unit_id": r.unit_id,
            "seasonal_score": _f(r.seasonal_score),
            "median_abs_delta": _f(r.median_abs_delta),
            "materiality_floor": _f(r.floor),
            "n_screened": n_screened,
        }

    if len(material):
        top = material.sort_values(["seasonal_score", "table_id"], ascending=[False, True]).iloc[0]
        out.append(
            Insight(
                id="W1:headline",
                params=params(top, True),
                n=int(top.n_history) if pd.notna(top.n_history) else None,
                window="same_calendar_month_revisions",
                robustness="robust",
                **_base("W1", "change_vs_prev", pairs[(top.table_id, top.commodity_id)], month, ts),
            )
        )
    for cid, (table, commodity) in US_SHEETS.items():
        my = _new_crop(con, month, table, commodity)
        sub = df[
            (df.table_id == table)
            & (df.commodity_id == commodity)
            & (df.attribute_id == "ending_stocks")
            & (df.market_year == my)
        ]
        if sub.empty:
            continue
        r = sub.iloc[0]
        out.append(
            Insight(
                id=f"W1:{cid}:ending_stocks",
                params=params(r, False),
                n=int(r.n_history) if pd.notna(r.n_history) else None,
                window="same_calendar_month_revisions",
                robustness="robust",
                **_base("W1", "change_vs_prev", cid, month, ts),
            )
        )
    return out, n_screened


def w2_stocks_to_use_rank(con: duckdb.DuckDBPyConnection, month: str, ts: str) -> list[Insight]:
    """W2: rank of the current new-crop stocks-to-use among the latest estimate of every MY
    from 2010/11 ("k-th tightest of n", 1 = tightest)."""
    out = []
    for cid, (table, commodity) in US_SHEETS.items():
        my = _new_crop(con, month, table, commodity)
        if my is None:
            continue
        cur = con.execute(
            """select stocks_to_use_pct, ending_stocks, unit_id from fct_balance_sheet
               where report_month = ? and table_id = ? and commodity_id = ?
                 and region_id = 'united_states' and market_year = ?""",
            [month, table, commodity, my],
        ).fetchone()
        hist = con.execute(
            f"""select market_year, max_by(stocks_to_use_pct, report_seq) as stu
                from fct_balance_sheet
                where table_id = ? and commodity_id = ? and region_id = 'united_states'
                  and regexp_matches(market_year, '{MY_RE}') and my_start >= ?
                  and market_year < ? and report_month <= ?
                group by market_year order by market_year""",
            [table, commodity, HISTORY_FIRST_MY, my, month],
        ).df()
        hist = hist[hist.stu.notna()]
        base = _base("W2", "stocks_to_use_rank", cid, month, ts)
        if cur is None or cur[0] is None or pd.isna(cur[0]):
            out.append(
                Insight(
                    id=f"W2:{cid}",
                    params={"market_year": my},
                    n=None,
                    window="my_2010_11_to_current",
                    robustness="robust",
                    suppressed_reason="no_data",
                    **base,
                )
            )
            continue
        stu = float(cur[0])
        k, n = stats.rank_low_first(stu, list(hist.stu))
        third = stats.tercile(k, n)
        out.append(
            Insight(
                id=f"W2:{cid}",
                params={
                    "table_id": table,
                    "market_year": my,
                    "stocks_to_use_pct": round(stu, 2),
                    "ending_stocks": _f(cur[1]),
                    "unit_id": cur[2],
                    "k": k,
                    "order": "tightest_first",
                    "tercile": {"low": "tight", "middle": "middle", "high": "loose"}[third],
                    "percentile_tighter_than": stats.percentile(k, n),
                    "first_market_year": hist.market_year.iloc[0] if len(hist) else my,
                    "history": [
                        {"market_year": m, "stocks_to_use_pct": round(float(v), 2)}
                        for m, v in zip(hist.market_year, hist.stu, strict=True)
                    ],
                },
                n=n,
                window="my_2010_11_to_current",
                robustness="robust",
                **base,
            )
        )
    return out


def w3_revision_rank(con: duckdb.DuckDBPyConnection, month: str, ts: str) -> list[Insight]:
    """W3: |Δ| of this report's new-crop U.S. ending stocks ranked among the same series'
    same-cycle-month |Δ| over MYs 2010/11+ (1 = largest)."""
    out = []
    for cid, (table, commodity) in US_SHEETS.items():
        my = _new_crop(con, month, table, commodity)
        if my is None:
            continue
        cur = con.execute(
            """select delta, cycle_month, series_key, unit_id, months_since_prev
               from fct_revisions
               where report_month = ? and table_id = ? and commodity_id = ?
                 and region_id = 'united_states' and attribute_id = 'ending_stocks'
                 and market_year = ?""",
            [month, table, commodity, my],
        ).fetchone()
        base = _base("W3", "revision_rank", cid, month, ts)
        if cur is None or cur[0] is None or pd.isna(cur[0]) or cur[1] is None:
            out.append(
                Insight(
                    id=f"W3:{cid}",
                    params={"market_year": my, "attribute_id": "ending_stocks"},
                    n=None,
                    window="same_cycle_month_my_2010_11_on",
                    robustness="robust",
                    suppressed_reason="first_projection",
                    **base,
                )
            )
            continue
        delta, cycle, series, unit = float(cur[0]), int(cur[1]), cur[2], cur[3]
        hist = con.execute(
            """select market_year, delta from fct_revisions
               where series_key = ? and cycle_month = ? and market_year < ? and my_start >= ?
                 and delta is not null and months_since_prev = 1
               order by market_year""",
            [series, cycle, my, HISTORY_FIRST_MY],
        ).df()
        k, n = stats.rank_high_first(abs(delta), [abs(v) for v in hist.delta])
        out.append(
            Insight(
                id=f"W3:{cid}",
                params={
                    "table_id": table,
                    "attribute_id": "ending_stocks",
                    "market_year": my,
                    "delta": delta,
                    "abs_delta": abs(delta),
                    "unit_id": unit,
                    "cycle_month": cycle,
                    "k": k,
                    "order": "largest_abs_first",
                    "percentile_larger_than": stats.percentile(k, n),
                    "history": [
                        {"market_year": m, "delta": float(v)}
                        for m, v in zip(hist.market_year, hist.delta, strict=True)
                    ],
                },
                n=n,
                window="same_cycle_month_my_2010_11_on",
                robustness="robust",
                **base,
            )
        )
    return out


def w4_brazil_soy_export_share(
    con: duckdb.DuckDBPyConnection, month: str, ts: str
) -> list[Insight]:
    """W4: Brazil ÷ the exporter rows present in the WASDE world soybean table (U.S., Brazil,
    Argentina, Paraguay when listed), current MY, ranked vs the latest estimate of prior MYs."""
    df = con.execute(
        f"""
        with x as (
            select report_month, report_seq, market_year, region_id, value
            from fct_wasde
            where table_id = 'world_soybeans' and commodity_id = 'soybeans'
              and attribute_id = 'exports' and period = 'annual' and reliability_stat is null
              and region_id in (select unnest($regions))
              and regexp_matches(market_year, '{MY_RE}') and my_start >= $first
              and report_month <= $month
        ),
        last_vintage as (
            select market_year, max(report_seq) as report_seq from x
            where region_id = 'brazil' group by market_year
        )
        select x.market_year, x.report_month, x.region_id, x.value
        from x join last_vintage using (market_year, report_seq)
        order by x.market_year, x.region_id
        """,
        {"regions": list(W4_EXPORTERS), "first": HISTORY_FIRST_MY, "month": month},
    ).df()
    base = _base("W4", "brazil_soy_export_share", "soybeans", month, ts)
    if df.empty:
        return [
            Insight(
                id="W4:soybeans",
                params={},
                n=None,
                window="my_2010_11_to_current",
                robustness="robust",
                suppressed_reason="no_data",
                **base,
            )
        ]
    shares = []
    for my, g in df.groupby("market_year", sort=True):
        vals = dict(zip(g.region_id, g.value, strict=True))
        denom = sum(vals.values())
        if "brazil" in vals and denom > 0:
            shares.append(
                {
                    "market_year": my,
                    "report_month": g.report_month.iloc[0],
                    "share": vals["brazil"] / denom,
                    "brazil": vals["brazil"],
                    "denominator": denom,
                    "countries": sorted(vals),
                }
            )
    cur = shares[-1]
    if cur["report_month"] != month:
        return []
    k, n = stats.rank_high_first(cur["share"], [s["share"] for s in shares[:-1]])
    caveats: list[Any] = ["local_marketing_years"]
    if len({tuple(s["countries"]) for s in shares}) > 1:
        caveats.append("partial_denominator")
    return [
        Insight(
            id="W4:soybeans",
            params={
                "market_year": cur["market_year"],
                "share": round(cur["share"], 4),
                "brazil_exports": cur["brazil"],
                "denominator_exports": round(cur["denominator"], 2),
                "unit_id": "mmt",
                "countries": cur["countries"],
                "k": k,
                "order": "highest_first",
                "percentile_higher_than": stats.percentile(k, n),
                "history": [
                    {
                        "market_year": s["market_year"],
                        "share": round(s["share"], 4),
                        "countries": s["countries"],
                    }
                    for s in shares[:-1]
                ],
            },
            n=n,
            window="my_2010_11_to_current",
            robustness="robust",
            caveats=caveats,
            **base,
        )
    ]
