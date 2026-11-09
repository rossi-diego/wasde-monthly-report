"""Analyst-friendly Excel workbooks (xlsxwriter): numeric cells, frozen panes, no merges."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import xlsxwriter
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from usda_reports.publish.focus import Focus
from usda_reports.publish.web_json import month_label, one

SOURCE = "USDA World Agricultural Supply and Demand Estimates (WASDE) · github.com/rossi-diego/usda-reports-dashboard"


class Styles:
    def __init__(self, wb: Workbook) -> None:
        self.title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#14532d"})
        self.bold = wb.add_format({"bold": True})
        self.muted = wb.add_format({"font_color": "#6b7280", "italic": True})
        self.head = wb.add_format(
            {"bold": True, "bg_color": "#ecfdf5", "bottom": 1, "text_wrap": True, "valign": "top"}
        )
        self.num = wb.add_format({"num_format": "#,##0.00;[Red]-#,##0.00"})
        self.num0 = wb.add_format({"num_format": "#,##0;[Red]-#,##0"})
        self.delta = wb.add_format(
            {"num_format": "+#,##0.00;[Red]-#,##0.00;0", "font_color": "#166534"}
        )
        self.pct = wb.add_format({"num_format": "+0.0%;[Red]-0.0%;0.0%"})
        self.label = wb.add_format({"indent": 1})


def _readme(ws: Worksheet, st: Styles, title: str, lines: list[tuple[str, Any]]) -> None:
    ws.set_column(0, 0, 28)
    ws.set_column(1, 1, 90)
    ws.write(0, 0, title, st.title)
    for i, (k, v) in enumerate(lines, start=2):
        ws.write(i, 0, k, st.bold)
        ws.write(i, 1, v)
    ws.write(len(lines) + 3, 0, SOURCE, st.muted)


def _table(
    ws: Worksheet, st: Styles, df: pd.DataFrame, first_row: int = 0, name: str | None = None
) -> None:
    """Write a DataFrame as an Excel Table (filterable, pivot-ready)."""
    if df.empty:
        ws.write(first_row, 0, "No data")
        return
    df = df.astype(object).where(pd.notna(df), None)
    columns = [{"header": str(c)} for c in df.columns]
    ws.add_table(
        first_row,
        0,
        first_row + len(df),
        len(df.columns) - 1,
        {
            "data": df.values.tolist(),
            "columns": columns,
            "name": name,
            "style": "Table Style Light 9",
        },
    )
    for i, c in enumerate(df.columns):
        width = min(max(len(str(c)), *(len(str(x)) for x in df[c].head(200))) + 2, 48)
        ws.set_column(i, i, width)
    ws.freeze_panes(first_row + 1, 0)


def _balance_sheet(
    ws: Worksheet,
    st: Styles,
    con: duckdb.DuckDBPyConnection,
    focus: Focus,
    month: str,
    prev: str | None,
    table: str,
    commodity: str,
    regions: list[str],
) -> None:
    row = 0
    for region in regions:
        cur = con.execute(
            "select * from fct_balance_sheet where report_month=? and table_id=? and commodity_id=? and region_id=? order by market_year",
            [month, table, commodity, region],
        ).df()
        if cur.empty:
            continue
        old = (
            con.execute(
                "select * from fct_balance_sheet where report_month=? and table_id=? and commodity_id=? and region_id=?",
                [prev, table, commodity, region],
            )
            .df()
            .set_index("market_year")
            if prev
            else pd.DataFrame()
        )
        ws.write(
            row,
            0,
            f"{cur.region.iat[0]} — {cur.commodity_label.iat[0]} ({cur.unit_label.iat[0]})",
            st.title,
        )
        row += 1
        ws.write(row, 0, "Line", st.head)
        col = 1
        for r in cur.itertuples():
            flag = (
                f" {r.proj_est_flag.title()}."
                if isinstance(r.proj_est_flag, str) and r.proj_est_flag
                else ""
            )
            for h in (
                f"{r.market_year}{flag} · {month_label(prev) if prev else 'prev.'}",
                f"{r.market_year}{flag} · {month_label(month)}",
                f"{r.market_year} · Change",
            ):
                ws.write(row, col, h, st.head)
                col += 1
        row += 1
        for line in focus.balance_lines:
            if line.id not in cur.columns or cur[line.id].isna().all():
                continue
            ws.write(row, 0, line.label.strip(), st.label)
            col = 1
            for _, r in cur.iterrows():
                v = r[line.id]
                p = (
                    old.at[r.market_year, line.id]
                    if (not old.empty and r.market_year in old.index)
                    else None
                )
                ws.write_number(row, col, p, st.num) if p is not None and pd.notna(
                    p
                ) else ws.write_blank(row, col, None)
                ws.write_number(row, col + 1, v, st.num) if pd.notna(v) else ws.write_blank(
                    row, col + 1, None
                )
                if p is not None and pd.notna(p) and pd.notna(v):
                    ws.write_number(row, col + 2, v - p, st.delta)
                col += 3
            row += 1
        row += 2
    ws.set_column(0, 0, 30)
    ws.set_column(1, 12, 16)
    ws.freeze_panes(2, 1)


def latest_report_workbook(
    con: duckdb.DuckDBPyConnection, focus: Focus, month: str, out: Path
) -> Path:
    rep = con.execute("select * from dim_reports order by report_seq").df()
    prev = rep.report_month.iloc[-2] if len(rep) > 1 else None
    meta = rep.iloc[-1]
    wb = xlsxwriter.Workbook(out, {"nan_inf_to_errors": True})
    st = Styles(wb)
    _readme(
        wb.add_worksheet("README"),
        st,
        f"WASDE {month_label(month)} — latest report vs previous",
        [
            ("Report", month_label(month)),
            ("WASDE number", int(meta.wasde_number) if pd.notna(meta.wasde_number) else ""),
            ("Released", str(meta.release_date)),
            ("Compared with", month_label(prev) if prev else "—"),
            (
                "Sheets",
                "Changes (every revised line, ranked) · one balance-sheet sheet per commodity · All data (long)",
            ),
            ("Flags", "Proj. = projection, Est. = estimate; blank = older marketing year"),
            (
                "Units",
                "Native WASDE units: U.S. tables in bushels/bales/short tons/pounds, world tables in million metric tons",
            ),
            (
                "Score",
                "|change| ÷ median |change| of the same line in the same calendar report month (>1 = larger than usual)",
            ),
            ("Generated", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")),
        ],
    )
    changes = con.execute(
        """
        select table_id as "Table", commodity_label as "Commodity", region as "Region",
               attribute_label as "Line", market_year as "Marketing year", coalesce(proj_est_flag, '') as "Flag",
               prev_value as "Previous", value as "Current", delta as "Change", pct_delta as "% change",
               unit_label as "Unit", round(seasonal_score, 2) as "Score", streak as "Streak"
        from fct_changes where report_month = ? and delta <> 0
        order by seasonal_score desc nulls last
        """,
        [month],
    ).df()
    ws = wb.add_worksheet("Changes")
    _table(ws, st, changes, name="changes")
    ws.set_column(6, 8, 14, st.num)
    ws.set_column(9, 9, 11, st.pct)

    for c in focus.commodities.values():
        _balance_sheet(
            wb.add_worksheet(f"{c.label} US"[:31]),
            st,
            con,
            focus,
            month,
            prev,
            c.us.table,
            c.us.commodity,
            ["united_states"],
        )
        _balance_sheet(
            wb.add_worksheet(f"{c.label} World"[:31]),
            st,
            con,
            focus,
            month,
            prev,
            c.world.table,
            c.world.commodity,
            ["world", "world_less_china", "brazil", "argentina", "china", "european_union"],
        )

    longdf = con.execute(
        """
        select table_label as "Table", commodity_label as "Commodity", region as "Region",
               attribute_label as "Line", coalesce(reliability_stat, '') as "Statistic",
               market_year as "Marketing year", coalesce(proj_est_flag, '') as "Flag", period as "Period",
               value as "Value", unit_label as "Unit"
        from fct_wasde where report_month = ?
        order by "Table", "Commodity", "Region", "Line", "Marketing year"
        """,
        [month],
    ).df()
    _table(wb.add_worksheet("All data (long)"), st, longdf, name="all_data")
    wb.close()
    return out


def history_workbook(con: duckdb.DuckDBPyConnection, focus: Focus, fid: str, out: Path) -> Path:
    c = focus.commodities[fid]
    wb = xlsxwriter.Workbook(out, {"nan_inf_to_errors": True})
    st = Styles(wb)
    first, last = one(con, "select min(report_month), max(report_month) from dim_reports")
    _readme(
        wb.add_worksheet("README"),
        st,
        f"{c.label} — WASDE revision history {month_label(first)} to {month_label(last)}",
        [
            (
                "Revision sheets",
                "Rows = report month, columns = marketing year. Read down a column to see how USDA's estimate for that year evolved.",
            ),
            ("U.S. source table", c.us.table),
            ("World source table", c.world.table),
            (
                "Stocks-to-use",
                "U.S.: ending stocks ÷ total use. World / World ex-China: ending stocks ÷ domestic use.",
            ),
            (
                "Balance sheets (long)",
                "Every published balance sheet line for this commodity, all reports, U.S. and all world regions.",
            ),
        ],
    )
    blocks = [
        ("US", c.us.table, c.us.commodity, "united_states"),
        ("World", c.world.table, c.world.commodity, "world"),
        ("World ex-China", c.world.table, c.world.commodity, "world_less_china"),
    ]
    for prefix, table, commodity, region in blocks:
        sheet = con.execute(
            "select * from fct_balance_sheet where table_id=? and commodity_id=? and region_id=? order by report_seq",
            [table, commodity, region],
        ).df()
        if sheet.empty:
            continue
        for attr, label in (
            ("ending_stocks", "ending stocks"),
            ("production", "production"),
            ("stocks_to_use_pct", "S-U %"),
            ("exports", "exports"),
        ):
            if sheet[attr].isna().all():
                continue
            pivot = sheet.pivot_table(
                index="report_month", columns="market_year", values=attr, aggfunc="first"
            )
            pivot = pivot[[m for m in pivot.columns if len(m) == 7]]
            ws = wb.add_worksheet(f"{prefix} {label}"[:31])
            units = sheet.unit_label.dropna()
            unit = "%" if attr == "stocks_to_use_pct" else (units.iat[0] if len(units) else "")
            ws.write(0, 0, f"{c.label} · {prefix} · {label} ({unit})", st.title)
            ws.write(1, 0, "Report", st.head)
            for j, my in enumerate(pivot.columns, start=1):
                ws.write(1, j, my, st.head)
            for i, (rm, vals) in enumerate(pivot.iterrows(), start=2):
                ws.write(i, 0, rm)
                for j, v in enumerate(vals, start=1):
                    if pd.notna(v):
                        ws.write_number(i, j, float(v), st.num)
            ws.set_column(0, 0, 10)
            ws.set_column(1, len(pivot.columns), 10)
            ws.freeze_panes(2, 1)
    longdf = con.execute(
        """
        select report_month as "Report", region as "Region", market_year as "Marketing year",
               coalesce(proj_est_flag, '') as "Flag", unit_label as "Unit",
               area_planted as "Area planted", area_harvested as "Area harvested", yield as "Yield",
               beginning_stocks as "Beginning stocks", production as "Production", imports as "Imports",
               total_supply as "Total supply", crush as "Crush", domestic_feed as "Feed",
               feed_residual as "Feed & residual", food_seed_industrial as "FSI", ethanol as "Ethanol",
               domestic_total as "Domestic use", exports as "Exports", total_use as "Total use",
               ending_stocks as "Ending stocks", round(stocks_to_use_pct, 2) as "Stocks-to-use %",
               farm_price as "Farm price", table_id as "Table"
        from fct_balance_sheet
        where (table_id = ? and commodity_id = ?) or (table_id = ? and commodity_id = ?)
        order by "Table", "Region", "Marketing year", "Report"
        """,
        [c.us.table, c.us.commodity, c.world.table, c.world.commodity],
    ).df()
    longdf = longdf.dropna(axis=1, how="all")
    _table(wb.add_worksheet("Balance sheets (long)"), st, longdf, name="balance_sheets")
    wb.close()
    return out
