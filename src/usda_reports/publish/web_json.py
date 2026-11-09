"""Static JSON + Parquet consumed by the Next.js site (written to web/public/data)."""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from usda_reports.publish.focus import Focus
from usda_reports.publish.highlights import (
    REGION_LABEL,
    build_highlights,
    first_projections,
    report_context,
)

REVISION_ATTRS = [
    "ending_stocks",
    "production",
    "stocks_to_use_pct",
    "exports",
    "domestic_total",
    "yield",
]
N_REVISION_YEARS = 8


def _clean(v: Any) -> Any:
    """JSON-safe scalars (NaN -> None, numpy -> python, round floats)."""
    if v is None:
        return None
    if isinstance(v, float | int) and not isinstance(v, bool):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4) if not f.is_integer() else (int(f) if abs(f) < 2**53 else f)
    if hasattr(v, "item"):
        return _clean(v.item())
    if isinstance(v, date | datetime):
        return v.isoformat()
    return v


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def walk(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list | tuple):
            return [walk(v) for v in o]
        return _clean(o)

    path.write_text(
        json.dumps(walk(obj), separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )


def one(
    con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> tuple[Any, ...]:
    """Run a query that must return exactly one row."""
    row = con.execute(sql, params or []).fetchone()
    if row is None:
        raise LookupError(f"query returned no rows: {sql[:80]}")
    return row


def month_label(m: str) -> str:
    return datetime.strptime(m + "-01", "%Y-%m-%d").strftime("%B %Y")


def cycle_month(report_month: str, my: str) -> int | None:
    if len(my) != 7 or my[4] != "/":
        return None
    y, mo = int(report_month[:4]), int(report_month[5:7])
    return (y - int(my[:4])) * 12 + (mo - 5)


# ── overview ─────────────────────────────────────────────────────────────────


def _sheet_rows(
    con: duckdb.DuckDBPyConnection, month: str, table: str, commodity: str, region: str
) -> pd.DataFrame:
    return con.execute(
        """
        select b.market_year, b.proj_est_flag, b.ending_stocks, b.stocks_to_use_pct, b.production,
               b.unit_id, b.unit_label,
               d.p_ending_stocks, d.d_ending_stocks, d.p_stocks_to_use_pct
        from fct_balance_sheet b
        left join fct_ending_stocks_drivers d
          using (report_month, table_id, commodity_id, region_id, market_year)
        where b.report_month = ? and b.table_id = ? and b.commodity_id = ? and b.region_id = ?
        order by b.market_year desc
        limit 2
        """,
        [month, table, commodity, region],
    ).df()


def _card_block(df: pd.DataFrame) -> dict[str, Any] | None:
    if df.empty:
        return None
    out: dict[str, Any] = {"unit": df.unit_id.iat[0], "unit_label": df.unit_label.iat[0]}
    for crop, (_, r) in zip(["new", "old"], df.iterrows(), strict=False):
        out[crop] = {
            "market_year": r.market_year,
            "flag": r.proj_est_flag,
            "ending_stocks": r.ending_stocks,
            "prev_ending_stocks": r.p_ending_stocks,
            "delta": r.d_ending_stocks,
            "stocks_to_use_pct": r.stocks_to_use_pct,
            "prev_stocks_to_use_pct": r.p_stocks_to_use_pct,
        }
    return out


def build_overview(con: duckdb.DuckDBPyConnection, focus: Focus, month: str) -> dict[str, Any]:
    cards = []
    for fid, c in focus.commodities.items():
        cards.append(
            {
                "commodity": fid,
                "label": c.label,
                "us": _card_block(
                    _sheet_rows(con, month, c.us.table, c.us.commodity, "united_states")
                ),
                "world_ex_china": _card_block(
                    _sheet_rows(con, month, c.world.table, c.world.commodity, "world_less_china")
                ),
                "world": _card_block(
                    _sheet_rows(con, month, c.world.table, c.world.commodity, "world")
                ),
            }
        )
    south_america = con.execute(
        """
        with r as (
            select commodity_id, region, region_id, market_year, value, prev_value, delta, unit_id,
                   dense_rank() over (partition by table_id order by market_year desc) as k
            from fct_revisions
            where report_month = ? and attribute_id = 'production'
              and table_id in ('world_soybeans', 'world_corn')
              and region_id in ('brazil', 'argentina')
        )
        select * exclude (k) from r where k <= 2 order by commodity_id desc, region_id desc, market_year desc
        """,
        [month],
    ).df()
    return {
        "report_month": month,
        "report_label": month_label(month),
        "context": report_context(month),
        "highlights": build_highlights(con, focus, month),
        "first_projections": first_projections(con, focus, month),
        "cards": cards,
        "south_america": south_america.to_dict("records"),
    }


# ── commodity pages ──────────────────────────────────────────────────────────


def _regions_for(
    con: duckdb.DuckDBPyConnection, focus: Focus, table: str, commodity: str, month: str
) -> list[str]:
    present = set(
        con.execute(
            "select distinct region_id from fct_balance_sheet where report_month = ? and table_id = ? and commodity_id = ?",
            [month, table, commodity],
        )
        .df()
        .region_id
    )
    return [r for r in focus.regions if r in present and r != "united_states"]


def build_series(
    con: duckdb.DuckDBPyConnection,
    focus: Focus,
    table: str,
    commodity: str,
    region: str,
    month: str,
) -> dict[str, Any]:
    sheet = con.execute(
        """
        select * from fct_balance_sheet
        where table_id = ? and commodity_id = ? and region_id = ?
        order by report_seq, market_year
        """,
        [table, commodity, region],
    ).df()
    latest = sheet[sheet.report_month == month].sort_values("market_year")
    line_units = dict(
        con.execute(
            """
            select attribute_id, any_value(unit_label) from fct_wasde
            where report_month = ? and table_id = ? and commodity_id = ? and region_id = ?
            group by attribute_id
            """,
            [month, table, commodity, region],
        ).fetchall()
    )
    line_units["stocks_to_use_pct"] = "%"
    prev_month = sheet.loc[sheet.report_month < month, "report_month"].max()
    prev = (
        sheet[sheet.report_month == prev_month].set_index("market_year")
        if isinstance(prev_month, str)
        else pd.DataFrame()
    )

    # Balance sheet (latest report, its 2–3 marketing years) with Δ vs previous report.
    columns = [{"market_year": r.market_year, "flag": r.proj_est_flag} for r in latest.itertuples()]
    rows = []
    for line in focus.balance_lines:
        if line.id not in latest.columns or latest[line.id].isna().all():
            continue
        vals = []
        for _, r in latest.iterrows():
            v = r[line.id]
            p = (
                prev.at[r.market_year, line.id]
                if (not prev.empty and r.market_year in prev.index)
                else None
            )
            vals.append(
                {
                    "value": v,
                    "prev": p,
                    "delta": (v - p) if (p is not None and pd.notna(p) and pd.notna(v)) else None,
                }
            )
        rows.append(
            {"id": line.id, "label": line.label, "unit": line_units.get(line.id), "values": vals}
        )

    # Drivers of the latest ending-stocks revision, per marketing year.
    drv = con.execute(
        """
        select * from fct_ending_stocks_drivers
        where report_month = ? and table_id = ? and commodity_id = ? and region_id = ?
        order by market_year
        """,
        [month, table, commodity, region],
    ).df()
    drivers = [
        {
            "market_year": d.market_year,
            "from": d.p_ending_stocks,
            "to": d.ending_stocks,
            "components": [
                {
                    "id": "beginning_stocks",
                    "label": "Beginning stocks",
                    "value": d.d_beginning_stocks,
                },
                *(
                    [
                        {
                            "id": "production_area",
                            "label": "Production · area",
                            "value": d.d_production_area,
                        },
                        {
                            "id": "production_yield",
                            "label": "Production · yield",
                            "value": d.d_production_yield,
                        },
                    ]
                    if pd.notna(d.d_production_area)
                    else [{"id": "production", "label": "Production", "value": d.d_production}]
                ),
                {"id": "imports", "label": "Imports", "value": d.d_imports},
                {"id": "domestic_total", "label": "Domestic use", "value": -d.d_domestic_total},
                {"id": "exports", "label": "Exports", "value": -d.d_exports},
                {"id": "other", "label": "Other / rounding", "value": d.d_other},
            ],
        }
        for d in drv.itertuples()
    ]

    # Revision paths for the most recent marketing years, aligned on cycle_month.
    mys = sorted(sheet.market_year.unique())
    recent = [m for m in mys if len(m) == 7][-N_REVISION_YEARS:]
    revisions: dict[str, list[dict[str, Any]]] = {}
    for attr in REVISION_ATTRS:
        if attr not in sheet.columns or sheet[attr].isna().all():
            continue
        series = []
        for my in recent:
            s = sheet[(sheet.market_year == my) & sheet[attr].notna()]
            if s.empty:
                continue
            series.append(
                {
                    "market_year": my,
                    "points": [
                        [
                            cycle_month(r["report_month"], my),
                            r[attr],
                            r["report_month"],
                            r["proj_est_flag"],
                        ]
                        for _, r in s.iterrows()
                    ],
                }
            )
        revisions[attr] = series

    # Stocks-to-use by marketing year: last published value (final) or current estimate.
    last = sheet.sort_values("report_seq").groupby("market_year").tail(1).sort_values("market_year")
    # Highlight only years still being projected/estimated; the oldest column is settled.
    current_mys = set(latest.loc[latest.proj_est_flag.isin(["proj", "est"]), "market_year"])
    su_hist = [
        {
            "market_year": r.market_year,
            "ending_stocks": r.ending_stocks,
            "stocks_to_use_pct": r.stocks_to_use_pct,
            "status": "current" if r.market_year in current_mys else "final",
            "flag": r.proj_est_flag if r.market_year in current_mys else None,
        }
        for r in last.itertuples()
        if len(r.market_year) == 7
    ]
    finals = [
        h["stocks_to_use_pct"]
        for h in su_hist
        if h["status"] == "final" and pd.notna(h["stocks_to_use_pct"])
    ]
    new_crop = su_hist[-1] if su_hist else None
    percentile = None
    if new_crop and finals and pd.notna(new_crop["stocks_to_use_pct"]) and len(finals) >= 10:
        percentile = sum(f <= new_crop["stocks_to_use_pct"] for f in finals) / len(finals)

    unit_id = (
        latest.unit_id.dropna().iat[0]
        if not latest.empty and latest.unit_id.notna().any()
        else None
    )
    unit_label = (
        latest.unit_label.dropna().iat[0]
        if not latest.empty and latest.unit_label.notna().any()
        else None
    )
    return {
        "table": table,
        "commodity": commodity,
        "region": region,
        "region_label": REGION_LABEL.get(
            region, latest.region.iat[0] if not latest.empty else region
        ),
        "report_month": month,
        "previous_report_month": prev_month if isinstance(prev_month, str) else None,
        "unit": unit_id,
        "unit_label": unit_label,
        "balance_sheet": {"columns": columns, "rows": rows},
        "drivers": drivers,
        "revisions": revisions,
        "stocks_to_use_history": su_hist,
        "stocks_to_use_percentile": percentile,
        "n_final_years": len(finals),
    }


def build_commodities(
    con: duckdb.DuckDBPyConnection, focus: Focus, month: str, out_dir: Path
) -> list[dict[str, Any]]:
    index = []
    for fid, c in focus.commodities.items():
        regions = [
            {
                "id": "united_states",
                "label": "United States",
                "table": c.us.table,
                "commodity": c.us.commodity,
            }
        ]
        for rid in _regions_for(con, focus, c.world.table, c.world.commodity, month):
            label = (
                REGION_LABEL.get(rid)
                or one(
                    con,
                    "select any_value(region) from fct_balance_sheet where region_id = ?",
                    [rid],
                )[0]
            )
            regions.append(
                {"id": rid, "label": label, "table": c.world.table, "commodity": c.world.commodity}
            )
        for r in regions:
            _dump(
                out_dir / "commodities" / fid / f"{r['id']}.json",
                build_series(con, focus, r["table"], r["commodity"], r["id"], month),
            )
        index.append({"id": fid, "label": c.label, "regions": regions})
    _dump(out_dir / "commodities" / "index.json", index)
    return index


# ── data explorer ────────────────────────────────────────────────────────────


def build_tables(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[dict[str, Any]]:
    """One compact Parquet per WASDE table for the in-browser explorer, plus a catalog."""
    folder = out_dir / "tables"
    folder.mkdir(parents=True, exist_ok=True)
    tables = con.execute(
        "select table_id, any_value(table_label) as label, count(*) as n from fct_wasde group by 1 order by 1"
    ).df()
    catalog = []
    for t in tables.itertuples():
        path = (folder / f"{t.table_id}.parquet").as_posix()
        con.execute(
            f"""
            copy (
                select report_month, commodity_label as commodity, region, attribute_label as attribute,
                       market_year, coalesce(proj_est_flag, '') as flag, period,
                       coalesce(reliability_stat, '') as stat, value, unit_label as unit
                from fct_wasde where table_id = ?
                order by commodity, region, attribute, market_year, report_month
            ) to '{path}' (format parquet, compression snappy, row_group_size 50000)
            """,
            [t.table_id],
        )
        dims = (
            con.execute(
                """
            select list(distinct commodity_label order by commodity_label) as commodities,
                   list(distinct region order by region) as regions,
                   list(distinct attribute_label order by attribute_label) as attributes,
                   list(distinct market_year order by market_year) as market_years,
                   min(report_month) as first_report, max(report_month) as last_report
            from fct_wasde where table_id = ?
            """,
                [t.table_id],
            )
            .df()
            .iloc[0]
        )
        catalog.append(
            {
                "id": t.table_id,
                "label": t.label,
                "rows": int(t.n),
                "file": f"tables/{t.table_id}.parquet",
                "bytes": Path(path).stat().st_size,
                **{
                    k: list(dims[k])
                    if k in {"commodities", "regions", "attributes", "market_years"}
                    else dims[k]
                    for k in dims.index
                },
            }
        )
    # WASDE table index for the explorer (catalog.json is the release catalogue).
    _dump(out_dir / "wasde_tables.json", catalog)
    return catalog


def build_meta(
    con: duckdb.DuckDBPyConnection,
    month: str,
    next_release: date | None,
    tag: str | None,
    downloads: list[dict[str, Any]],
) -> dict[str, Any]:
    rep = con.execute("select * from dim_reports order by report_seq").df()
    latest = rep.iloc[-1]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "latest": {
            "report_month": month,
            "label": month_label(month),
            "wasde_number": latest.wasde_number,
            "release_date": latest.release_date,
        },
        "previous_report_month": rep.iloc[-2].report_month if len(rep) > 1 else None,
        "next_release": next_release.isoformat() if next_release else None,
        "history": {
            "first_report": rep.iloc[0].report_month,
            "reports": len(rep),
            "rows": int(rep.n_rows.sum()),
        },
        "data_release_tag": tag,
        "downloads": downloads,
    }
