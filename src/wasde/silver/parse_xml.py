"""Parse ESMIS WASDE XML (SSRS export, 2010-07+) into the raw long schema.

The XML does not label commodity/unit for most tables and spreads the market year,
forecast month, region and attribute across different element attributes depending on
the page. We flatten every value cell with its inherited context, keep only the
current-month column, then translate positions to CSV vocabulary using the layout learned
from months where both formats exist (see ``xml_layout``).

Reliability tables are skipped here (their values are attributes, not cells); they are
available from the CSV for 2021+.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd
from lxml import etree

from wasde.silver import RAW_COLUMNS
from wasde.silver.text import (
    clean_label,
    flag_from_text,
    market_year_label,
    parse_number,
    squash,
)

_ATTR_KEY = re.compile(r"^(?:m\d+_)?(.*?)\d*$")
_VALUE_KEYS = {"cell_value", "wb_value"}
_SR = re.compile(r"sr\d+")
_MATRIX = re.compile(r"matrix\d+")
_WASDE_NO = re.compile(r"WASDE\s*-\s*(\d+)", re.IGNORECASE)
_MONTH_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_QUARTERS = {"I": "Q1", "II": "Q2", "III": "Q3", "IV": "Q4"}


@dataclass(frozen=True)
class XmlCell:
    xtitle: str
    matrix: str
    xcom: str
    xreg: str
    xattr: str
    market_year_raw: str
    forecast_month: str
    subtitle: str
    page_title: str
    value_raw: str


def _first(ctx: dict[str, str], *keys: str) -> str:
    for k in keys:
        v = ctx.get(k)
        if v is not None and squash(v):
            return v
    return ""


def flatten(path: Path | bytes) -> list[XmlCell]:
    """Every value cell with the context inherited from its ancestors."""
    root = etree.fromstring(path if isinstance(path, bytes) else path.read_bytes())
    cells: list[XmlCell] = []

    def walk(el: etree._Element, ctx: dict[str, str], matrix: str) -> None:
        ctx = dict(ctx)
        values = []
        for k, v in el.attrib.items():
            m = _ATTR_KEY.match(str(k))
            base = m.group(1) if m else str(k)
            if base in _VALUE_KEYS:
                values.append(str(v))
            else:
                ctx[base] = str(v)
        # Two releases (2010-07, 2015-01) carry an XML namespace: "{wasde}matrix1".
        tag = etree.QName(el).localname if isinstance(el.tag, str) else ""
        if _MATRIX.fullmatch(tag):
            matrix = tag
        elif _SR.fullmatch(tag) and not matrix:
            matrix = ""
        for v in values:
            cells.append(
                XmlCell(
                    xtitle=clean_label(ctx.get("sub_report_title")),
                    matrix=matrix or "none",
                    xcom=clean_label(_first(ctx, "commodity", "attribute_group")),
                    xreg=clean_label(_first(ctx, "region", "commodity_header")),
                    xattr=clean_label(_first(ctx, "attribute", "attr_desc")),
                    market_year_raw=squash(_first(ctx, "market_year", "region_header")),
                    forecast_month=squash(_first(ctx, "forecast_month", "wb_forecast_month_desc")),
                    subtitle=clean_label(ctx.get("sub_report_subtitle")).strip("()"),
                    page_title=squash(ctx.get("page_title")),
                    value_raw=v,
                )
            )
        for child in el:
            walk(child, ctx, matrix)

    walk(root, {}, "")
    return cells


def is_current_column(forecast_month: str, report_month: str) -> bool:
    """Blank (history columns), quarter labels, or the report's own month."""
    fm = forecast_month.strip()
    if not fm or fm in _QUARTERS:
        return True
    return fm.lower().startswith(_MONTH_ABBR[int(report_month[5:7]) - 1])


def cells_frame(cells: list[XmlCell], report_month: str) -> pd.DataFrame:
    """Current-column cells as a DataFrame with parsed value / MY / flag / period."""
    rows = []
    for c in cells:
        if not is_current_column(c.forecast_month, report_month):
            continue
        v = parse_number(c.value_raw)
        if v is None:
            continue
        rows.append(
            {
                "xtitle": c.xtitle,
                "matrix": c.matrix,
                "xcom": c.xcom,
                "xreg": c.xreg,
                "xattr": c.xattr,
                "market_year": market_year_label(c.market_year_raw),
                "proj_est_flag": flag_from_text(c.market_year_raw),
                "period": _QUARTERS.get(c.forecast_month.strip(), "annual"),
                "subtitle": c.subtitle,
                "page_title": c.page_title,
                "value": v,
            }
        )
    return pd.DataFrame(rows)


def wasde_number_from(frame: pd.DataFrame) -> int | None:
    for t in frame.get("page_title", pd.Series(dtype=str)).dropna().unique():
        m = _WASDE_NO.search(str(t))
        if m:
            return int(m.group(1))
    return None


def parse_xml(
    source: Path | bytes,
    report_month: str,
    release_date: date | None,
    layout: XmlLayoutProtocol,
) -> pd.DataFrame:
    frame = cells_frame(flatten(source), report_month)
    if frame.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    mapped = layout.apply(frame)
    mapped["report_month"] = report_month
    mapped["wasde_number"] = pd.array([wasde_number_from(frame)] * len(mapped), dtype="Int64")
    mapped["release_date"] = release_date
    mapped["reliability_stat"] = ""
    mapped["source"] = "esmis_xml"
    return mapped[RAW_COLUMNS].reset_index(drop=True)


class XmlLayoutProtocol(Protocol):
    def apply(self, frame: pd.DataFrame) -> pd.DataFrame: ...
