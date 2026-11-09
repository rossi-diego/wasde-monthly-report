"""Site JSON for the Export Sales page: ``web/public/data/reports/export_sales/``.

* ``index.json``: commodities with data, latest release, next release.
* ``<commodity>.json``: latest week KPIs, the point-in-time USDA target, the pace series of
  the current MY and the 5 prior MYs (each as % of the USDA projection public at the time),
  weekly net sales of the current MY, and the top destinations (China and unknown always
  listed). Every number comes from gold; nothing is computed in the browser but formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from usda_reports.core.logs import get_logger
from usda_reports.publish.web_json import _dump

log = get_logger(__name__)

COMMODITIES = ("soybeans", "corn", "wheat", "soybean_meal", "soybean_oil")
TOP_N = 10
SCHEMA_VERSION = 1


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


def _labels(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return dict(con.execute("select commodity_id, label from dim_commodity").fetchall())


def commodity_payload(
    con: duckdb.DuckDBPyConnection, cid: str, label: str, next_release: str | None
) -> dict[str, Any] | None:
    pace = con.execute(
        "select * from fct_export_pace where commodity_id = ? order by week_ending", [cid]
    ).df()
    if pace.empty:
        return None
    cur_my = int(pace.esr_market_year.max())
    cur_rows = pace[pace.esr_market_year == cur_my].sort_values("week_ending")
    cur = cur_rows.iloc[-1]
    hist_years = list(range(cur_my - 5, cur_my))
    series = []
    for my in [*hist_years, cur_my]:
        g = pace[pace.esr_market_year == my].sort_values("week_of_my")
        if g.empty:
            continue
        series.append(
            {
                "market_year": g.market_year.iloc[0],
                "esr_market_year": my,
                "current": my == cur_my,
                # [week_of_my, pct_of_target (null without an as-of target), wasde_release_key]
                "points": [
                    [int(r.week_of_my), _f(r.pct_of_target, 5), r.wasde_release_key]
                    for r in g.itertuples()
                ],
            }
        )
    band = [
        [
            int(r.week_of_my),
            _f(r.pct_5yr_mean, 5),
            _f(r.pct_5yr_min, 5),
            _f(r.pct_5yr_max, 5),
            int(r.n_5yr),
        ]
        for r in cur_rows.itertuples()
    ]
    weekly = [
        {
            "week_ending": _d(r.week_ending),
            "week_of_my": int(r.week_of_my),
            "release_key": r.release_key,
            "net_sales_mt": _f(r.net_sales_mt),
            "weekly_exports_mt": _f(r.weekly_exports_mt),
            "next_my_net_sales_mt": _f(r.next_my_net_sales_mt),
            "net_sales_4wk_avg_mt": _f(r.net_sales_4wk_avg_mt, 1),
        }
        for r in cur_rows.itertuples()
    ]
    dest = con.execute(
        """select country_id, country_label, total_commitment_mt, accumulated_exports_mt,
                  outstanding_sales_mt, net_sales_mt
           from fct_export_sales_weekly
           where commodity_id = ? and esr_market_year = ? and week_ending = ?
           order by total_commitment_mt desc, country_id""",
        [cid, cur_my, cur.week_ending],
    ).df()
    total = float(dest.total_commitment_mt.sum()) if len(dest) else 0.0
    top = dest.head(TOP_N)
    must = dest[dest.country_id.isin(["china", "unknown"]) & ~dest.country_id.isin(top.country_id)]
    shown = pd.concat([top, must])
    rows = [
        {
            "country_id": r.country_id,
            "country_label": r.country_label,
            "total_commitment_mt": _f(r.total_commitment_mt),
            "accumulated_exports_mt": _f(r.accumulated_exports_mt),
            "outstanding_sales_mt": _f(r.outstanding_sales_mt),
            "net_sales_mt": _f(r.net_sales_mt),
            "share": _f(r.total_commitment_mt / total, 5) if total else None,
        }
        for r in shown.itertuples()
    ]
    china_unknown_hist = [
        {
            "market_year": r.market_year,
            "china_share": _f(r.china_commitment_mt / r.total_commitment_mt, 5)
            if r.total_commitment_mt
            else None,
            "unknown_share": _f(r.unknown_commitment_mt / r.total_commitment_mt, 5)
            if r.total_commitment_mt
            else None,
        }
        for r in pace[
            (pace.week_of_my == cur.week_of_my) & pace.esr_market_year.isin(hist_years)
        ].itertuples()
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "commodity_id": cid,
        "label": label,
        "unit_id": "mt",
        "market_year": cur.market_year,
        "esr_market_year": cur_my,
        "latest": {
            "release_key": cur.release_key,
            "release_ts_utc": _ts(cur.release_ts_utc),
            "release_ts_source": cur.release_ts_source,
            "week_ending": _d(cur.week_ending),
            "week_of_my": int(cur.week_of_my),
            "vintage_quality": cur.vintage_quality,
        },
        "next_release": next_release,
        "target": {
            "wasde_release_key": cur.wasde_release_key
            if isinstance(cur.wasde_release_key, str)
            else None,
            "wasde_release_ts_utc": _ts(cur.wasde_release_ts_utc),
            "exports_mt": _f(cur.wasde_exports_mt, 1),
            "exports_native": _f(cur.wasde_exports_native),
            "unit_id": cur.wasde_unit_id if isinstance(cur.wasde_unit_id, str) else None,
            "flag": cur.wasde_proj_est_flag if isinstance(cur.wasde_proj_est_flag, str) else None,
        },
        "kpis": {
            "total_commitment_mt": _f(cur.total_commitment_mt),
            "accumulated_exports_mt": _f(cur.accumulated_exports_mt),
            "outstanding_sales_mt": _f(cur.outstanding_sales_mt),
            "net_sales_mt": _f(cur.net_sales_mt),
            "weekly_exports_mt": _f(cur.weekly_exports_mt),
            "next_my_net_sales_mt": _f(cur.next_my_net_sales_mt),
            "next_my_outstanding_mt": _f(cur.next_my_outstanding_mt),
            "net_sales_4wk_avg_mt": _f(cur.net_sales_4wk_avg_mt, 1),
            "pct_of_target": _f(cur.pct_of_target, 5),
            "pct_shipped": _f(cur.pct_shipped, 5),
            "weeks_remaining": int(cur.weeks_remaining),
            "required_weekly_sales_mt": _f(cur.required_weekly_sales_mt, 1),
            "n_5yr": int(cur.n_5yr),
            "pct_5yr_mean": _f(cur.pct_5yr_mean, 5),
            "pct_5yr_min": _f(cur.pct_5yr_min, 5),
            "pct_5yr_max": _f(cur.pct_5yr_max, 5),
        },
        "pace": {
            # Legend contract: history = % of the USDA projection public at the time.
            "basis": "pct_of_usda_projection_at_the_time",
            "series": series,
            # [week_of_my, mean, min, max, n] of the 5 prior MYs at each current week.
            "band": band,
        },
        "weekly": weekly,
        "destinations": {
            "week_ending": _d(cur.week_ending),
            "total_commitment_mt": total,
            "n_destinations": len(dest),
            "rows": rows,
            "other_mt": total - float(shown.total_commitment_mt.sum()),
            "china_unknown_history": china_unknown_hist,
        },
    }


def build_export_sales(
    con: duckdb.DuckDBPyConnection, out_dir: Path, next_release: str | None
) -> dict[str, Any] | None:
    """Write the Export Sales page JSON; returns the index (None when ESR has no data)."""
    if not con.execute(
        "select count(*) from information_schema.tables where table_name = 'fct_export_pace'"
    ).fetchone()[0]:  # type: ignore[index]
        return None
    labels = _labels(con)
    folder = out_dir / "reports" / "export_sales"
    items = []
    latest: dict[str, Any] = {}
    for cid in COMMODITIES:
        payload = commodity_payload(con, cid, labels.get(cid, cid), next_release)
        if payload is None:
            continue
        _dump(folder / f"{cid}.json", payload)
        items.append(
            {
                "id": cid,
                "label": payload["label"],
                "market_year": payload["market_year"],
                "file": f"reports/export_sales/{cid}.json",
            }
        )
        latest = max(latest, payload["latest"], key=lambda x: x.get("release_key") or "")
    if not items:
        return None
    index = {
        "schema_version": SCHEMA_VERSION,
        "report_id": "export_sales",
        "latest": latest,
        "next_release": next_release,
        "commodities": items,
    }
    _dump(folder / "index.json", index)
    log.info("publish.export_sales", commodities=len(items), release=latest.get("release_key"))
    return index
