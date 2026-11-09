"""Publish everything from gold: site JSON, explorer Parquet, Excel and full-dataset files."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from wasde.config import Settings
from wasde.logs import get_logger
from wasde.manifest import Manifest
from wasde.publish.excel import history_workbook, latest_report_workbook
from wasde.publish.focus import Focus
from wasde.publish.web_json import (
    _dump,
    build_commodities,
    build_meta,
    build_overview,
    build_tables,
    one,
)
from wasde.sources.calendar import load_calendar

log = get_logger(__name__)

FULL_COLUMNS = """
    report_month, wasde_number, release_date, source, table_id, table_label,
    commodity_id, commodity_label, region_id, region, attribute_id, attribute_label,
    reliability_stat, market_year, proj_est_flag, period, value, unit_id, unit_label
"""


def _full_dataset(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[Path]:
    pq = (out_dir / "wasde_full.parquet").as_posix()
    csv = (out_dir / "wasde_full.csv.gz").as_posix()
    query = f"select {FULL_COLUMNS} from fct_wasde order by report_month, table_id, commodity_id, region_id, attribute_id, market_year"
    con.execute(f"copy ({query}) to '{pq}' (format parquet, compression zstd)")
    con.execute(f"copy ({query}) to '{csv}' (header, compression gzip)")
    return [Path(pq), Path(csv)]


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


def publish_all(
    settings: Settings,
    manifest: Manifest,
    tag: str | None,
    repo: str = "rossi-diego/usda-reports-dashboard",
) -> None:
    focus = Focus.load(settings.config_dir / "focus.yaml")
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
    pq, csv = _full_dataset(con, pub)
    files += [
        (
            pq,
            "Full dataset (Parquet)",
            "Every value of every report since July 2010, harmonized (≈850k rows).",
        ),
        (
            csv,
            "Full dataset (CSV, gzip)",
            "Same as Parquet; exceeds Excel's row limit — use Python/R/Power BI.",
        ),
    ]
    dl = web / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    for path, _, _ in files:
        shutil.copy2(path, dl / path.name)

    dates = load_calendar(settings.config_dir / "release_calendar.yaml")
    today = datetime.now(UTC).date()
    nxt = next((d for d in dates if d > today), None)
    meta = build_meta(con, month, nxt, tag, _downloads(files, tag, repo))
    _dump(web / "meta.json", meta)
    shutil.copy2(web / "meta.json", pub / "meta.json")
    con.close()

    manifest.latest_report = month
    manifest.latest_wasde_number = int(wasde_no) if wasde_no is not None else None
    manifest.total_rows = int(rows)
    if tag:
        manifest.data_release_tag = tag
    log.info("publish.done", month=month, rows=rows, files=len(files), web=str(web))
