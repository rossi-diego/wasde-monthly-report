"""Publish everything from gold: site JSON, explorer Parquet, Excel and the download catalogue."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.calendar import load_calendar
from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest
from usda_reports.publish.catalogue import write_catalogue
from usda_reports.publish.excel import history_workbook, latest_report_workbook
from usda_reports.publish.focus import Focus
from usda_reports.publish.web_json import (
    _dump,
    build_commodities,
    build_meta,
    build_overview,
    build_tables,
    one,
)

log = get_logger(__name__)

REPORT_ID = "wasde"


def _downloads(
    files: list[tuple[Path, str, str]], tag: str | None, repo: str
) -> list[dict[str, Any]]:
    out = []
    for path, label, desc in files:
        out.append(
            {
                "file": path.name,
                "label": label,
                "description": desc,
                "bytes": path.stat().st_size,
                "url": f"downloads/{path.name}",
                "release_url": f"https://github.com/{repo}/releases/download/{tag}/{path.name}"
                if tag
                else None,
            }
        )
    return out


def reports_meta(
    con: duckdb.DuckDBPyConnection, next_release: str | None
) -> dict[str, dict[str, Any]]:
    """``meta.json['reports']``: latest release per report (from dim_release)."""
    out: dict[str, dict[str, Any]] = {}
    rows = con.execute(
        """select report_id, release_key, strftime(release_ts_utc at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
                  (select sum(n_rows) from dim_release d2 where d2.report_id = d.report_id)
           from dim_release d where is_latest order by report_id"""
    ).fetchall()
    for rid, key, ts, n in rows:
        out[rid] = {
            "latest_release_key": key,
            "release_ts_utc": ts,
            "next_release": next_release if rid == REPORT_ID else None,
            "rows": int(n),
        }
    return out


def publish_all(
    settings: Settings,
    manifest: Manifest,
    tag: str | None,
    repo: str = "rossi-diego/usda-reports-dashboard",
) -> None:
    focus = Focus.load(settings.report_config_dir(REPORT_ID) / "focus.yaml")
    # Same configuration as dbt's handle (read-write) so both can coexist in one process.
    con = duckdb.connect(str(settings.duckdb_path))
    month, wasde_no, rows = one(
        con,
        "select max(report_month), max_by(wasde_number, report_month), (select count(*) from fct_wasde) from dim_reports",
    )

    web = settings.web_data_dir
    shutil.rmtree(web, ignore_errors=True)
    web.mkdir(parents=True, exist_ok=True)
    pub = settings.publish_dir
    shutil.rmtree(pub, ignore_errors=True)
    pub.mkdir(parents=True, exist_ok=True)

    build_commodities(con, focus, month, web)
    _dump(web / "overview.json", build_overview(con, focus, month))
    build_tables(con, web)

    files: list[tuple[Path, str, str]] = [
        (
            latest_report_workbook(con, focus, month, pub / f"wasde_{month}_latest.xlsx"),
            "Latest report (Excel)",
            "What changed vs last month, balance sheets per commodity, full long table.",
        ),
    ]
    for fid, c in focus.commodities.items():
        files.append(
            (
                history_workbook(con, focus, fid, pub / f"wasde_history_{fid}.xlsx"),
                f"{c.label} history (Excel)",
                "Revision matrices since 2010 and every balance sheet, U.S. and world.",
            )
        )
    # Versioned catalogue (release assets) + the legacy wasde_full.* aliases (also on the site).
    write_catalogue(con, pub)
    files += [
        (
            pub / "wasde_full.parquet",
            "Full dataset (Parquet)",
            "Every value of every report since July 2010, harmonized (≈850k rows).",
        ),
        (
            pub / "wasde_full.csv.gz",
            "Full dataset (CSV, gzip)",
            "Same as Parquet; exceeds Excel's row limit — use Python/R/Power BI.",
        ),
    ]
    dl = web / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    for path, _, _ in files:
        shutil.copy2(path, dl / path.name)

    dates = load_calendar(settings.calendars_dir / f"{REPORT_ID}.yaml")
    today = datetime.now(UTC).date()
    nxt = next((d for d in dates if d > today), None)
    meta = build_meta(con, month, nxt, tag, _downloads(files, tag, repo))
    meta["reports"] = reports_meta(con, nxt.isoformat() if nxt else None)
    _dump(web / "meta.json", meta)
    shutil.copy2(web / "meta.json", pub / "meta.json")
    con.close()

    state = manifest.report(REPORT_ID)
    state.latest_release_key = month
    state.latest_number = int(wasde_no) if wasde_no is not None else None
    state.total_rows = int(rows)
    if tag:
        manifest.data_release_tag = tag
    log.info("publish.done", month=month, rows=rows, files=len(files), web=str(web))
