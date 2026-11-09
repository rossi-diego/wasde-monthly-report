"""Publish everything from gold: site JSON, explorer Parquet, Excel, the download catalogue,
``datapackage.json``, ``catalog.json`` and ``insights.json``."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.calendar import load_calendar, parse_time_et, release_datetime_utc
from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest
from usda_reports.core.registry import Registry, load_registry
from usda_reports.gold import dbt_target_dir
from usda_reports.insights import engine as insights_engine
from usda_reports.publish.catalog import build_catalog
from usda_reports.publish.catalogue import (
    ALL_DATASETS,
    SITE_PREVIEW_MAX_BYTES,
    dataset_by_stem,
    write_catalogue,
)
from usda_reports.publish.datapackage import build_datapackage, write_datapackage
from usda_reports.publish.excel import history_workbook, latest_report_workbook
from usda_reports.publish.focus import Focus
from usda_reports.publish.web_export_sales import build_export_sales
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
REPO = "rossi-diego/usda-reports-dashboard"


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


def next_releases(settings: Settings, registry: Registry, now: datetime) -> dict[str, str | None]:
    """Next scheduled release date per enabled report.

    WASDE keeps its historical rule (first date after today) because ``meta.next_release`` is
    part of the Soy Outlook contract; other reports use the release instant (time in ET).
    """
    out: dict[str, str | None] = {}
    for cfg in registry.enabled():
        dates = load_calendar(settings.calendars_dir / f"{cfg.id}.yaml")
        if cfg.id == REPORT_ID:
            nxt = next((d for d in dates if d > now.date()), None)
        else:
            at = parse_time_et(cfg.release_time_et)
            nxt = next((d for d in dates if release_datetime_utc(d, at) > now), None)
        out[cfg.id] = nxt.isoformat() if nxt else None
    return out


def reports_meta(
    con: duckdb.DuckDBPyConnection, next_release: dict[str, str | None] | str | None
) -> dict[str, dict[str, Any]]:
    """``meta.json['reports']``: latest release per report (from dim_release).

    ``next_release`` is a per-report map (a single string is accepted for WASDE only)."""
    if not isinstance(next_release, dict):
        next_release = {REPORT_ID: next_release}
    out: dict[str, dict[str, Any]] = {}
    rows = con.execute(
        """select report_id, release_key, strftime(release_ts_utc at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
                  (select sum(n_rows) from dim_release d2 where d2.report_id = d.report_id),
                  (select count(*) from dim_release d3 where d3.report_id = d.report_id)
           from dim_release d where is_latest order by report_id"""
    ).fetchall()
    for rid, key, ts, n, releases in rows:
        out[rid] = {
            "latest_release_key": key,
            "release_ts_utc": ts,
            "next_release": next_release.get(rid),
            "rows": int(n),
            "releases": int(releases),
        }
    return out


def publish_all(
    settings: Settings,
    manifest: Manifest,
    tag: str | None,
    repo: str = REPO,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    registry = load_registry(settings.config_dir)
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
    entries = write_catalogue(con, pub, ALL_DATASETS)
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
    # Small catalogue Parquet files are also served by the site (previews, ≤ 5 MB each).
    site_files = {p.name for p, _, _ in files}
    for e in entries:
        stem = e["file"].split(".", 1)[0]
        if e["format"] != "parquet" or e.get("legacy_alias_of"):
            continue
        if dataset_by_stem(stem).site_preview and e["bytes"] <= SITE_PREVIEW_MAX_BYTES:
            shutil.copy2(pub / e["file"], dl / e["file"])
            site_files.add(e["file"])

    nxt = next_releases(settings, registry, now)
    build_export_sales(con, web, nxt.get("export_sales"))

    wasde_next = nxt.get(REPORT_ID)
    meta = build_meta(
        con,
        month,
        datetime.fromisoformat(wasde_next).date() if wasde_next else None,
        tag,
        _downloads(files, tag, repo),
    )
    meta["reports"] = reports_meta(con, nxt)
    _dump(web / "meta.json", meta)
    shutil.copy2(web / "meta.json", pub / "meta.json")

    doc = insights_engine.build(con, settings, tag, now)
    insights_engine.write(doc, web / "insights.json")
    shutil.copy2(web / "insights.json", pub / "insights.json")
    con.close()

    package = build_datapackage(
        entries, pub, dbt_target_dir(settings) / "manifest.json", registry, tag, repo
    )
    write_datapackage(package, pub / "datapackage.json")
    shutil.copy2(pub / "datapackage.json", web / "datapackage.json")
    _dump(
        web / "catalog.json",
        build_catalog(entries, tag, repo, registry, meta["reports"], site_files),
    )
    shutil.copy2(web / "catalog.json", pub / "catalog.json")

    state = manifest.report(REPORT_ID)
    state.latest_release_key = month
    state.latest_number = int(wasde_no) if wasde_no is not None else None
    state.total_rows = int(rows)
    for rid, m in meta["reports"].items():
        if rid == REPORT_ID:
            continue
        s = manifest.report(rid)
        s.latest_release_key = m["latest_release_key"]
        s.total_rows = m["rows"]
    if tag:
        manifest.data_release_tag = tag
    log.info("publish.done", month=month, rows=rows, files=len(entries), web=str(web))
