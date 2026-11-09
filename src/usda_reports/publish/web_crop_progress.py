"""Site JSON for the Crop Progress page: ``web/public/data/reports/crop_progress/``.

* ``index.json``: latest release and week, next release, season state, the crop files.
* ``<crop>.json`` (corn, soybeans, winter_wheat, spring_wheat): the newest week's stages (with
  NASS's published previous-week, previous-year and 5-year-average columns), the newest
  condition (five ratings, good-to-excellent, condition index, NASS's previous-year values and
  the own 5-year comparison), and the three chapter series of the current season:
  good-to-excellent vs the 5-year band (by week), stage pace vs NASS's 5-year average (the
  stage in progress), and the condition index vs the 5-year band. Every number comes from
  gold; the browser only formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.logs import get_logger
from usda_reports.insights.rules.common import day, num, text, ts
from usda_reports.insights.rules.crop_progress import (
    CROPS,
    HISTORY_START,
    SeasonInfo,
    crop_season,
    pick_stage,
)
from usda_reports.publish.web_json import _dump

log = get_logger(__name__)

SCHEMA_VERSION = 1
REPORT_ID = "crop_progress"
LABELS = {
    "corn": "Corn",
    "soybeans": "Soybeans",
    "winter_wheat": "Winter wheat",
    "spring_wheat": "Spring wheat",
}


def _exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "select count(*) from information_schema.tables where table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def _r(v: Any, nd: int) -> float | None:
    x = num(v)
    return None if x is None else round(x, nd)


def crop_payload(
    con: duckdb.DuckDBPyConnection,
    crop: str,
    stage_order: list[str],
    si: SeasonInfo | None,
    next_release: str | None,
) -> dict[str, Any] | None:
    prog = con.execute(
        "select * from fct_crop_progress_weekly where crop = ? and kind = 'progress' "
        "order by week_ending",
        [crop],
    ).df()
    cond = con.execute(
        "select * from fct_crop_condition where crop = ? order by week_ending", [crop]
    ).df()
    if prog.empty and cond.empty:
        return None
    season = int(max(prog.season.max() if len(prog) else 0, cond.season.max() if len(cond) else 0))
    rank = {s: i for i, s in enumerate(stage_order)}
    latest_week = prog.week_ending.max() if len(prog) else None
    cur_stages = prog[prog.week_ending == latest_week] if latest_week is not None else prog
    stages = cur_stages.assign(_o=cur_stages.category.map(rank).fillna(99)).sort_values("_o")
    active = pick_stage(cur_stages, stage_order) if len(cur_stages) else None
    season_prog = prog[prog.season == season]
    stage_series = (
        season_prog[season_prog.category == active.category]
        if active is not None
        else season_prog[:0]
    )
    season_cond = cond[cond.season == season]
    last_cond = cond.iloc[-1] if len(cond) else None
    commodity = str(prog.commodity_id.iloc[0]) if len(prog) else str(cond.commodity_id.iloc[0])
    newest = prog.iloc[-1] if len(prog) else last_cond
    assert newest is not None
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "crop": crop,
        "commodity_id": commodity,
        "label": LABELS.get(crop, crop),
        "history_start": HISTORY_START,
        "season": season,
        "season_state": si.state if si else None,
        # "crop": this crop's season is complete while the report's is open (spring wheat
        # after harvest): final values, not stale, and not in the next release.
        "season_scope": si.scope if si else None,
        "latest": {
            "release_key": text(newest.first_release_key) or text(newest.release_key),
            "release_ts_utc": ts(newest.first_release_ts_utc)
            if "first_release_ts_utc" in newest
            else ts(newest.release_ts_utc),
            "week_ending": day(newest.week_ending),
            "vintage_quality": "as_published",
        },
        "next_release": next_release,
        "n_states": int(newest.n_states) if num(newest.n_states) is not None else None,
        "stages": [
            {
                "stage": r.category,
                "value_pct": num(r.value_pct),
                "nass_prev_week_pct": num(r.nass_prev_week_pct),
                "nass_prev_year_pct": num(r.nass_prev_year_pct),
                "nass_5yr_avg_pct": num(r.nass_5yr_avg_pct),
                "vs_5yr_avg_pp": num(r.vs_5yr_avg_pp),
                "avg_years": text(r.avg_years),
            }
            for r in stages.itertuples()
        ],
        "week_ending": day(latest_week) if latest_week is not None else None,
        "condition": None
        if last_cond is None
        else {
            "week_ending": day(last_cond.week_ending),
            "release_key": text(last_cond.first_release_key),
            "very_poor_pct": num(last_cond.very_poor_pct),
            "poor_pct": num(last_cond.poor_pct),
            "fair_pct": num(last_cond.fair_pct),
            "good_pct": num(last_cond.good_pct),
            "excellent_pct": num(last_cond.excellent_pct),
            "ge_pct": num(last_cond.ge_pct),
            "ci": _r(last_cond.ci, 3),
            "nass_prev_week_ge_pct": num(last_cond.nass_prev_week_ge_pct),
            "nass_prev_year_ge_pct": num(last_cond.nass_prev_year_ge_pct),
            "nass_prev_year_ci": _r(last_cond.nass_prev_year_ci, 3),
            "n_5yr": int(last_cond.n_5yr),
            "ge_5yr_mean": _r(last_cond.ge_5yr_mean, 1),
            "ge_5yr_min": num(last_cond.ge_5yr_min),
            "ge_5yr_max": num(last_cond.ge_5yr_max),
            "ci_5yr_mean": _r(last_cond.ci_5yr_mean, 3),
            "ci_5yr_min": _r(last_cond.ci_5yr_min, 3),
            "ci_5yr_max": _r(last_cond.ci_5yr_max, 3),
        },
        # Chapter 1: [week_ending, ge_pct, nass_prev_year_ge_pct, 5yr mean, min, max, n]
        "ge": {
            "basis": "own_5yr_same_week_by_day_of_year",
            "series": [
                [
                    day(r.week_ending),
                    num(r.ge_pct),
                    num(r.nass_prev_year_ge_pct),
                    _r(r.ge_5yr_mean, 1),
                    num(r.ge_5yr_min),
                    num(r.ge_5yr_max),
                    int(r.n_5yr),
                ]
                for r in season_cond.itertuples()
            ],
        },
        # Chapter 2: the stage in progress, [week_ending, value_pct, nass_5yr_avg_pct,
        # nass_prev_year_pct] per week of the season (NASS's average as published).
        "stage_pace": {
            "basis": "nass_5yr_average_as_published",
            "stage": active.category if active is not None else None,
            "avg_years": text(active.avg_years) if active is not None else None,
            "series": [
                [
                    day(r.week_ending),
                    num(r.value_pct),
                    num(r.nass_5yr_avg_pct),
                    num(r.nass_prev_year_pct),
                ]
                for r in stage_series.itertuples()
            ],
        },
        # Chapter 3: [week_ending, ci, 5yr mean, min, max, n]
        "ci": {
            "basis": "own_5yr_same_week_by_day_of_year",
            "series": [
                [
                    day(r.week_ending),
                    _r(r.ci, 3),
                    _r(r.ci_5yr_mean, 3),
                    _r(r.ci_5yr_min, 3),
                    _r(r.ci_5yr_max, 3),
                    int(r.n_5yr),
                ]
                for r in season_cond.itertuples()
            ],
        },
    }


def build_crop_progress(
    con: duckdb.DuckDBPyConnection,
    out_dir: Path,
    next_release: str | None,
    stage_order: dict[str, list[str]],
    si: SeasonInfo | None,
) -> dict[str, Any] | None:
    """Write the Crop Progress page JSON; returns the index (None when there is no data)."""
    if not _exists(con, "fct_crop_condition"):
        return None
    folder = out_dir / "reports" / REPORT_ID
    items = []
    latest: dict[str, Any] = {}
    for crop in CROPS:
        order = stage_order.get(crop, [])
        csi = crop_season(con, si, crop, order) if si is not None else None
        payload = crop_payload(con, crop, order, csi, next_release)
        if payload is None:
            continue
        _dump(folder / f"{crop}.json", payload)
        items.append(
            {
                "id": crop,
                "commodity_id": payload["commodity_id"],
                "label": payload["label"],
                "week_ending": payload["week_ending"],
                "file": f"reports/{REPORT_ID}/{crop}.json",
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
        "season": None
        if si is None
        else {
            "state": si.state,
            "season": si.season,
            "last_scheduled": si.last_scheduled.isoformat() if si.last_scheduled else None,
        },
        "crops": items,
    }
    _dump(folder / "index.json", index)
    log.info("publish.crop_progress", crops=len(items), release=latest.get("release_key"))
    return index
