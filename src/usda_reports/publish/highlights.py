"""Monthly highlights: the few revisions in the latest report that actually matter.

Rules (from the trader review, see config/reports/wasde/focus.yaml):
1. Candidates: key balance-sheet lines of the focus commodities, U.S. tables + world regions,
   new-crop and old-crop marketing years only.
2. Absolute materiality floor per series; below it a change is never a headline.
3. Score = |Δ| / median |Δ| of the same series in the same calendar report month
   (seasonal z-like score). Falls back to |%Δ| / 2% when history is thin.
4. One headline per commodity × region × MY (ending stocks preferred, drivers attached),
   max N per commodity, top K overall.
5. May reports also get "first projection" items for the new marketing year.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from usda_reports.publish import fmt
from usda_reports.publish.focus import Focus

REGION_LABEL = {"united_states": "U.S.", "world": "World", "world_less_china": "World ex-China"}
ORDINAL = {2: "2nd", 3: "3rd"}
# Context chips under a headline, most explanatory first.
RELATED_ORDER = [
    "yield",
    "area_harvested",
    "production",
    "exports",
    "crush",
    "ending_stocks",
    "farm_price",
]

REPORT_CONTEXT = {
    1: "January report: final U.S. production estimates for the previous harvest.",
    5: "May report: USDA's first projections for the new marketing year.",
    6: "June report: last update before the June 30 Acreage and Grain Stocks reports.",
    7: "July report: incorporates the June 30 Acreage and Grain Stocks reports.",
    8: "August report: first survey-based U.S. yields for corn and soybeans.",
    9: "September report: updated yields; incorporates the Sept. 1 grain stocks for old crop.",
    10: "October report: yields updated as harvest advances; Sept. 30 Grain Stocks applied.",
    11: "November report: harvest-time yield update.",
    12: "December report: South American crops come into focus.",
}


def report_context(report_month: str) -> str | None:
    return REPORT_CONTEXT.get(int(report_month[5:7]))


def _focus_lookup(focus: Focus) -> dict[tuple[str, str], tuple[str, str]]:
    """(table_id, commodity_id) -> (focus id, scope)."""
    out = {}
    for fid, c in focus.commodities.items():
        out[(c.us.table, c.us.commodity)] = (fid, "us")
        out[(c.world.table, c.world.commodity)] = (fid, "world")
    return out


def _candidates(con: duckdb.DuckDBPyConnection, focus: Focus, month: str) -> pd.DataFrame:
    tables = sorted(focus.tables())
    rules = focus.highlights
    return con.execute(
        """
        with recent_my as (
            select table_id, market_year,
                   dense_rank() over (partition by table_id order by market_year desc) as my_rank
            from (select distinct table_id, market_year from fct_changes
                  where report_month = $month and regexp_matches(market_year, '^[0-9]{4}/[0-9]{2}$'))
        )
        select c.*, b.stocks_to_use_pct, m.my_rank
        from fct_changes c
        join recent_my m using (table_id, market_year)
        join fct_balance_sheet b using (report_month, table_id, commodity_id, region_id, market_year)
        where c.report_month = $month
          and m.my_rank <= 2
          and c.table_id in (select unnest($tables))
          and c.attribute_id in (select unnest($attrs))
          and c.region_id in (select unnest($regions))
          and not (c.table_id like 'world_%' and c.region_id = 'united_states')
          and c.delta <> 0
        """,
        {"month": month, "tables": tables, "attrs": rules.attributes, "regions": rules.regions},
    ).df()


def _drivers(con: duckdb.DuckDBPyConnection, month: str) -> dict[tuple, dict[str, Any]]:
    df = con.execute("select * from fct_ending_stocks_drivers where report_month = ?", [month]).df()
    return {
        (r.table_id, r.commodity_id, r.region_id, r.market_year): r._asdict()
        for r in df.itertuples(index=False)
    }


def _driver_text(d: dict[str, Any], unit_id: str) -> str:
    parts = []

    # Effect on ending stocks (same convention as the waterfall): more use or exports
    # *reduces* stocks, so those lines enter with a minus sign.
    def neg(v: Any) -> Any:
        return None if v is None or pd.isna(v) else -v

    raw: list[tuple[str, Any]] = [
        ("production", d.get("d_production")),
        ("exports", neg(d.get("d_exports"))),
        ("domestic use", neg(d.get("d_domestic_total"))),
        ("beginning stocks", d.get("d_beginning_stocks")),
        ("imports", d.get("d_imports")),
    ]
    comps = [(n, float(v)) for n, v in raw if v is not None and pd.notna(v) and abs(v) > 1e-9]
    comps.sort(key=lambda kv: abs(kv[1]), reverse=True)
    for name, v in comps[:3]:
        text = f"{name} {fmt.delta(v, unit_id)}"
        if name == "production":
            dy, da = d.get("d_yield"), d.get("d_area_harvested")
            bits = []
            if dy is not None and pd.notna(dy) and abs(dy) > 1e-9:
                bits.append(
                    f"yield {fmt.delta(dy, 'bu_per_acre' if unit_id == 'm_bu' else 'lb_per_acre')}"
                )
            if da is not None and pd.notna(da) and abs(da) > 1e-9:
                bits.append(f"area {fmt.delta(da, 'm_acres')}")
            if bits:
                text += f" ({', '.join(bits)})"
        parts.append(text)
    return ", ".join(parts)


def _sentence(r: pd.Series, driver: dict[str, Any] | None) -> str:
    region = REGION_LABEL.get(r.region_id, r.region)
    verb = "raised" if r.delta > 0 else "cut"
    what = f"{region} {r.commodity_label.lower()} {r.market_year} {r.attribute_label.lower()}"
    pct = (
        f" ({fmt.pct(r.pct_delta)})"
        if pd.notna(r.pct_delta) and r.attribute_id in {"ending_stocks", "production"}
        else ""
    )
    s = f"USDA {verb} {what} by {fmt.delta(r.delta, r.unit_id).lstrip('+−')}{pct} to {fmt.quantity(r.value, r.unit_id)}."
    if driver and r.attribute_id == "ending_stocks":
        dt = _driver_text(driver, r.unit_id)
        if dt:
            s += f" Effect on stocks: {dt}."
        su, psu = driver.get("stocks_to_use_pct"), driver.get("p_stocks_to_use_pct")
        if su is not None and psu is not None and pd.notna(su) and pd.notna(psu):
            s += f" Stocks-to-use {su:.1f}% vs {psu:.1f}%."
    if r.streak and r.streak >= 2:
        n = int(r.streak)
        word = "raise" if r.delta > 0 else "cut"
        s += f" {ORDINAL.get(n, f'{n}th')} consecutive {word}."
    return s


def build_highlights(
    con: duckdb.DuckDBPyConnection, focus: Focus, month: str
) -> list[dict[str, Any]]:
    rules = focus.highlights
    cand = _candidates(con, focus, month)
    if cand.empty:
        return []
    lookup = _focus_lookup(focus)
    cand["focus_id"] = [
        lookup.get((t, c), (None, None))[0]
        for t, c in zip(cand.table_id, cand.commodity_id, strict=True)
    ]
    cand["scope"] = [
        lookup.get((t, c), (None, None))[1]
        for t, c in zip(cand.table_id, cand.commodity_id, strict=True)
    ]
    cand = cand[cand.focus_id.notna()].copy()

    floors = [
        rules.floor(s, f, a)
        for s, f, a in zip(cand.scope, cand.focus_id, cand.attribute_id, strict=True)
    ]
    cand["floor"] = floors
    material = [
        (abs(d) >= fl) if fl is not None else (pd.notna(p) and abs(p) >= 0.02)
        for d, fl, p in zip(cand.delta, cand.floor, cand.pct_delta, strict=True)
    ]
    cand = cand[material].copy()
    if cand.empty:
        return []
    # Blend "unusual for this time of year" with "big in economic terms" so a line that rarely
    # moves (e.g. ethanol in October) cannot outrank an 18% cut to ending stocks.
    magnitude = (cand.pct_delta.abs() / 0.02).clip(upper=12)
    seasonal = cand.seasonal_score.where(cand.n_history >= 3).clip(upper=12)
    cand["score"] = (0.5 * seasonal.fillna(magnitude) + 0.5 * magnitude.fillna(seasonal)).fillna(
        0.0
    )
    cand.loc[cand.attribute_id == "ending_stocks", "score"] *= 1.3
    cand.loc[cand.region_id.isin(rules.primary_regions), "score"] *= 1.4
    cand.loc[cand.my_rank == 1, "score"] *= 1.1  # new crop matters a bit more

    drivers = _drivers(con, month)
    best = (
        cand.sort_values("score", ascending=False)
        .groupby(["focus_id", "region_id", "market_year"], sort=False)
        .head(1)
    )
    # World and World ex-China usually tell the same story: keep the stronger of the two.
    group = best.region_id.replace({"world_less_china": "world"})
    best = best.assign(_group=group).drop_duplicates(
        ["focus_id", "attribute_id", "market_year", "_group"]
    )
    items: list[dict[str, Any]] = []
    per_commodity: dict[str, int] = {}
    for _, r in best.sort_values("score", ascending=False).iterrows():
        if per_commodity.get(r.focus_id, 0) >= rules.max_per_commodity:
            continue
        driver = drivers.get((r.table_id, r.commodity_id, r.region_id, r.market_year))
        related = cand[
            (cand.focus_id == r.focus_id)
            & (cand.region_id == r.region_id)
            & (cand.market_year == r.market_year)
            & (cand.attribute_id != r.attribute_id)
        ]
        items.append(
            {
                "commodity": r.focus_id,
                "commodity_label": focus.commodities[r.focus_id].label,
                "region_id": r.region_id,
                "region": REGION_LABEL.get(r.region_id, r.region),
                "market_year": r.market_year,
                "crop": "new" if r.my_rank == 1 else "old",
                "attribute": r.attribute_id,
                "attribute_label": r.attribute_label,
                "value": float(r.value),
                "prev_value": float(r.prev_value),
                "delta": float(r.delta),
                "pct_delta": None if pd.isna(r.pct_delta) else float(r.pct_delta),
                "unit": r.unit_id,
                "unit_label": r.unit_label,
                "score": round(float(r.score), 2),
                "streak": int(r.streak or 0),
                "stocks_to_use_pct": None
                if pd.isna(r.stocks_to_use_pct)
                else round(float(r.stocks_to_use_pct), 2),
                "related": [
                    {
                        "attribute": x.attribute_id,
                        "label": x.attribute_label,
                        "delta": float(x.delta),
                        "unit": x.unit_id,
                    }
                    for x in sorted(
                        related.itertuples(index=False),
                        key=lambda x: (
                            RELATED_ORDER.index(x.attribute_id)
                            if x.attribute_id in RELATED_ORDER
                            else len(RELATED_ORDER)
                        ),
                    )
                ][:4],
                "sentence": _sentence(r, driver),
            }
        )
        per_commodity[r.focus_id] = per_commodity.get(r.focus_id, 0) + 1
        if len(items) >= rules.max_items:
            break
    return items


def first_projections(
    con: duckdb.DuckDBPyConnection, focus: Focus, month: str
) -> list[dict[str, Any]]:
    """In May: the new marketing year's first U.S. ending-stocks projection vs the old crop."""
    if month[5:7] != "05":
        return []
    out = []
    for fid, c in focus.commodities.items():
        df = con.execute(
            """
            select market_year, ending_stocks, stocks_to_use_pct, unit_id from fct_balance_sheet
            where report_month = ? and table_id = ? and commodity_id = ? and region_id = 'united_states'
            order by market_year desc limit 2
            """,
            [month, c.us.table, c.us.commodity],
        ).df()
        if len(df) < 2:
            continue
        new, old = df.iloc[0], df.iloc[1]
        out.append(
            {
                "commodity": fid,
                "market_year": new.market_year,
                "value": float(new.ending_stocks),
                "unit": new.unit_id,
                "sentence": (
                    f"First look at {new.market_year}: U.S. {c.label.lower()} ending stocks projected at "
                    f"{fmt.quantity(new.ending_stocks, new.unit_id)} vs {fmt.quantity(old.ending_stocks, old.unit_id)} "
                    f"for {old.market_year}."
                ),
            }
        )
    return out
