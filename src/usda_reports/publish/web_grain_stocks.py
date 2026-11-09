"""Site JSON for the Grain Stocks page: ``web/public/data/reports/grain_stocks/``.

* ``index.json``: latest release and stock date, next release, the commodity files.
* ``<commodity>.json`` (corn, soybeans, wheat): the newest stock date by position, the three
  chapters (stocks of the current marketing year vs the 5-year range per stock date; G1 NASS
  vs the as-of WASDE ending stocks on every ending-stock date since 2010; G2 implied
  disappearance of recent quarters vs the same quarter of the 5 prior years) and the last 12
  stock dates. Million bushels; every number comes from gold.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from usda_reports.core.logs import get_logger
from usda_reports.insights import stats
from usda_reports.insights.rules.common import day, num, text, ts
from usda_reports.insights.rules.grain_stocks import COMMODITIES, HISTORY_START, to_mbu
from usda_reports.publish.web_json import _dump

log = get_logger(__name__)

SCHEMA_VERSION = 1
REPORT_ID = "grain_stocks"
LABELS = {"corn": "Corn", "soybeans": "Soybeans", "wheat": "Wheat (all classes)"}
QUARTERS_SHOWN = 12
SHARE_DP = 6


def _exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "select count(*) from information_schema.tables where table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def _band(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"mean": None, "min": None, "max": None, "n": 0}
    return {
        "mean": round(stats.mean(values) or 0, 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "n": len(values),
    }


def commodity_payload(
    con: duckdb.DuckDBPyConnection, cid: str, next_release: str | None
) -> dict[str, Any] | None:
    q = con.execute(
        "select * from fct_grain_stocks_quarterly where commodity_id = ? order by as_of_date", [cid]
    ).df()
    if q.empty:
        return None
    cur = q.iloc[-1]
    my = int(cur.my_start)
    # Chapter 1: each stock date of the current MY vs the same date of the 5 prior MYs.
    by_quarter = []
    for qn in (1, 2, 3, 4):
        now_rows = q[(q.my_start == my) & (q.quarter_of_my == qn)]
        hist = q[(q.my_start >= my - 5) & (q.my_start <= my - 1) & (q.quarter_of_my == qn)]
        by_quarter.append(
            {
                "quarter_of_my": qn,
                "as_of_date": day(now_rows.as_of_date.iloc[0]) if len(now_rows) else None,
                "total_mbu": to_mbu(now_rows.total_kbu.iloc[0]) if len(now_rows) else None,
                "band_mbu": _band([float(v) / 1000 for v in hist.total_kbu]),
                "history": [
                    {"market_year": r.market_year, "total_mbu": to_mbu(r.total_kbu)}
                    for r in hist.itertuples()
                ],
            }
        )
    g1 = con.execute(
        "select * from fct_stocks_vs_wasde where commodity_id = ? order by as_of_date", [cid]
    ).df()
    g2 = con.execute(
        "select * from fct_stocks_disappearance where commodity_id = ? order by as_of_date", [cid]
    ).df()
    disappearance = []
    for r in g2.tail(8).itertuples():
        hist = g2[
            (g2.quarter_of_my == r.quarter_of_my)
            & (g2.my_start >= r.my_start - 5)
            & (g2.my_start <= r.my_start - 1)
            & g2.implied_disappearance_kbu.notna()
        ]
        disappearance.append(
            {
                "as_of_date": day(r.as_of_date),
                "prev_as_of_date": day(r.prev_as_of_date),
                "quarter_of_my": int(r.quarter_of_my),
                "market_year": r.market_year,
                "release_key": r.release_key,
                "is_harvest_quarter": bool(r.is_harvest_quarter),
                "prev_stocks_mbu": to_mbu(r.prev_stocks_kbu),
                "production_mbu": to_mbu(r.production_kbu),
                "wasde_release_key": text(r.wasde_release_key),
                "stocks_mbu": to_mbu(r.stocks_kbu),
                "implied_disappearance_mbu": to_mbu(r.implied_disappearance_kbu),
                "band_mbu": _band([float(v) / 1000 for v in hist.implied_disappearance_kbu]),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "commodity_id": cid,
        "label": LABELS.get(cid, cid),
        "history_start": HISTORY_START,
        "unit_id": "m_bu",
        "market_year": cur.market_year,
        "latest": {
            "release_key": cur.latest_release_key,
            "release_ts_utc": ts(cur.latest_release_ts_utc),
            "as_of_date": day(cur.as_of_date),
            "quarter_of_my": int(cur.quarter_of_my),
            "vintage_quality": "as_published",
        },
        "next_release": next_release,
        "kpis": {
            "total_mbu": to_mbu(cur.total_kbu),
            "on_farm_mbu": to_mbu(cur.on_farm_kbu),
            "off_farm_mbu": to_mbu(cur.off_farm_kbu),
            "total_mt": round(float(cur.total_mt)) if num(cur.total_mt) is not None else None,
            "on_farm_share": None
            if num(cur.on_farm_share) is None
            else round(float(cur.on_farm_share), SHARE_DP),
            "total_yoy_pct": None
            if num(cur.total_yoy_pct) is None
            else round(float(cur.total_yoy_pct), SHARE_DP),
        },
        "by_quarter": by_quarter,
        "vs_wasde": {
            "basis": "wasde_ending_stocks_public_at_release",
            "rows": [
                {
                    "market_year": r.market_year,
                    "as_of_date": day(r.as_of_date),
                    "release_key": r.release_key,
                    "nass_total_mbu": None
                    if pd.isna(r.nass_total_mbu)
                    else round(float(r.nass_total_mbu), 3),
                    "wasde_release_key": text(r.wasde_release_key),
                    "wasde_ending_stocks_mbu": num(r.wasde_ending_stocks_mbu),
                    "surprise_mbu": None
                    if pd.isna(r.surprise_mbu)
                    else round(float(r.surprise_mbu), 3),
                    "surprise_pct": None
                    if pd.isna(r.surprise_pct)
                    else round(float(r.surprise_pct), SHARE_DP),
                }
                for r in g1.itertuples()
            ],
        },
        "disappearance": disappearance,
        "quarters": [
            {
                "as_of_date": day(r.as_of_date),
                "market_year": r.market_year,
                "quarter_of_my": int(r.quarter_of_my),
                "on_farm_mbu": to_mbu(r.on_farm_kbu),
                "off_farm_mbu": to_mbu(r.off_farm_kbu),
                "total_mbu": to_mbu(r.total_kbu),
                "total_first_mbu": to_mbu(r.total_first_kbu),
                "is_revised": bool(r.is_revised),
                "first_release_key": r.first_release_key,
            }
            for r in q.tail(QUARTERS_SHOWN).itertuples()
        ],
    }


def build_grain_stocks(
    con: duckdb.DuckDBPyConnection, out_dir: Path, next_release: str | None
) -> dict[str, Any] | None:
    """Write the Grain Stocks page JSON; returns the index (None when there is no data)."""
    if not _exists(con, "fct_grain_stocks_quarterly"):
        return None
    folder = out_dir / "reports" / REPORT_ID
    items = []
    latest: dict[str, Any] = {}
    for cid in COMMODITIES:
        payload = commodity_payload(con, cid, next_release)
        if payload is None:
            continue
        _dump(folder / f"{cid}.json", payload, nd=SHARE_DP)
        items.append(
            {
                "id": cid,
                "label": payload["label"],
                "as_of_date": payload["latest"]["as_of_date"],
                "file": f"reports/{REPORT_ID}/{cid}.json",
            }
        )
        latest = max(latest, payload["latest"], key=lambda x: x.get("release_key") or "")
    if not items:
        return None
    index = {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "latest": latest,
        "next_release": next_release,
        "history_start": HISTORY_START,
        "commodities": items,
    }
    _dump(folder / "index.json", index)
    log.info("publish.grain_stocks", commodities=len(items), release=latest.get("release_key"))
    return index
