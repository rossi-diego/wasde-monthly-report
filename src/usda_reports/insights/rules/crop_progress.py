"""Crop Progress insights C1–C3 and the off-season state (plan §6). National ("<N> States")
rows of corn, soybeans, winter wheat and spring wheat; history from the 2010-06-07 release.

* C1 good_excellent: GE = good% + excellent% vs NASS's published previous-year value and vs an
  own 5-year comparison (the last 5 seasons at the week within ±3 days by day of year, because
  NASS publishes no 5-year average for condition).
* C2 stage_pace: pct_stage − NASS's own published 5-year average (used as published).
* C3 condition_index: CI = (1·VP + 2·P + 3·F + 4·G + 5·E)/100 (1–5) vs the same own 5 years.
* Off-season: after the season's final weekly release (or once the season's last scheduled
  date is more than a week past) the season is ``closed``: C1 keeps the crop's final rating
  ("Season closed: final GE X% vs 5-yr Y%") and is exempt from the staleness gate; C2/C3 are
  suppressed with ``season_closed``. The home page hides the card from December to March.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

import duckdb
import pandas as pd

from usda_reports.core.calendar import load_calendar
from usda_reports.core.config import Settings
from usda_reports.insights.rules.common import day, num, range_params, rnd, text, ts
from usda_reports.insights.schema import InputRef, Insight

REPORT_ID = "crop_progress"
CROPS = ("corn", "soybeans", "winter_wheat", "spring_wheat")
WINDOW_OWN_5Y = "prior_5_seasons_same_week_doy_pm3"
WINDOW_NASS_5Y = "nass_published_5yr_average"
WINDOW_FINAL_5Y = "prior_5_seasons_final_rating"
# NASS's published 5-year average is a mean of 5 seasons.
NASS_AVG_N = 5
# How long after the season's last scheduled release the season counts as closed even if that
# final release never arrived (cadence).
CLOSE_AFTER_DAYS = 7
HISTORY_START = "2010-06-07"

SeasonState = Literal["in_season", "closed"]


@dataclass(frozen=True)
class SeasonInfo:
    state: SeasonState
    season: int  # calendar year of the newest release
    latest_release_key: str
    last_scheduled: date | None  # the season's last scheduled release date


def season_info(latest_release_key: str, calendar: list[date], now: datetime) -> SeasonInfo:
    """In season or closed, from the newest ingested release and the release calendar.

    Closed when the newest release is the season's final scheduled one (within 3 days: a
    holiday Tuesday counts), or when that final date is more than a week past (the report
    ended without it), or when the newest release belongs to an earlier year than ``now``
    and the new season has not started yet."""
    latest = date.fromisoformat(latest_release_key)
    season = latest.year
    in_year = [d for d in calendar if d.year == season]
    last = max(in_year) if in_year else None
    today = now.date()
    closed = (
        last is None
        or latest >= last - timedelta(days=3)
        or today > last + timedelta(days=CLOSE_AFTER_DAYS)
        or today.year > season
    )
    return SeasonInfo("closed" if closed else "in_season", season, latest_release_key, last)


def season_for(
    con: duckdb.DuckDBPyConnection, settings: Settings, now: datetime
) -> SeasonInfo | None:
    """Season state from the newest ingested release and config/calendars/crop_progress.yaml
    (None when Crop Progress has no release in gold)."""
    key = latest_release_key(con)
    if key is None:
        return None
    return season_info(key, load_calendar(settings.calendars_dir / "crop_progress.yaml"), now)


def stage_orders(settings: Settings) -> dict[str, list[str]]:
    """Stages per crop in crop-calendar order (config/reports/crop_progress/source.yaml)."""
    from usda_reports.reports.crop_progress.source import SourceConfig

    cfg = SourceConfig.load(settings.report_config_dir(REPORT_ID) / "source.yaml")
    return {crop: cfg.stage_order(crop) for crop in cfg.stages}


def latest_release_key(con: duckdb.DuckDBPyConnection) -> str | None:
    row = con.execute(
        "select max(release_key) from dim_release where report_id = 'crop_progress'"
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _season_params(si: SeasonInfo) -> dict[str, Any]:
    return {
        "season_state": si.state,
        "season": si.season,
        "season_last_scheduled": si.last_scheduled.isoformat() if si.last_scheduled else None,
        "history_start": HISTORY_START,
    }


def _latest_condition(con: duckdb.DuckDBPyConnection, crop: str) -> pd.Series | None:
    df = con.execute(
        "select * from fct_crop_condition where crop = ? and ge_pct is not null "
        "order by week_ending desc limit 1",
        [crop],
    ).df()
    return None if df.empty else df.iloc[0]


def condition_history(con: duckdb.DuckDBPyConnection, cur: pd.Series) -> pd.DataFrame:
    """The crop's rated weeks in the 5 previous seasons within ±3 days by day of year (the
    same rule as fct_crop_condition's n_5yr)."""
    return con.execute(
        """select season, week_ending, ge_pct, ci, release_key
           from fct_crop_condition
           where crop = ? and season between ? and ? and ge_pct is not null
             and abs(dayofyear(week_ending) - dayofyear(cast(? as date))) <= 3
           order by season""",
        [cur.crop, int(cur.season) - 5, int(cur.season) - 1, day(cur.week_ending)],
    ).df()


def final_ratings(con: duckdb.DuckDBPyConnection, cur: pd.Series) -> pd.DataFrame:
    """The crop's final rated week of each of the 5 previous seasons (season-closed C1:
    "final GE X% vs 5-yr Y%" compares final with final, not the same calendar week)."""
    return con.execute(
        """select season, week_ending, ge_pct, ci, release_key
           from fct_crop_condition
           where crop = ? and season between ? and ? and ge_pct is not null
           qualify row_number() over (partition by season order by week_ending desc) = 1
           order by season""",
        [cur.crop, int(cur.season) - 5, int(cur.season) - 1],
    ).df()


def _condition_common(cur: pd.Series, si: SeasonInfo) -> dict[str, Any]:
    return {
        "crop": cur.crop,
        "season": int(cur.season),
        "week_ending": day(cur.week_ending),
        "release_key": text(cur.first_release_key) or text(cur.release_key),
        "n_states": int(cur.n_states) if num(cur.n_states) is not None else None,
        "unit_id": "pct",
        **_season_params(si),
        "final": si.state == "closed",
    }


def _caveats(crop: str, own_5y: bool, final: bool = False) -> list[Any]:
    out: list[Any] = ["nass_selected_states_aggregate"]
    if final:
        out.append("own_5yr_final_rating")
    elif own_5y:
        out.append("own_5yr_same_week_by_day_of_year")
    else:
        out.append("nass_5yr_average_as_published")
    if crop == "winter_wheat":
        out.append("winter_wheat_fall_ratings_next_crop")
    return out


def _inputs(cur: pd.Series) -> list[InputRef]:
    key = text(cur.first_release_key) or text(cur.release_key)
    return [InputRef(report_id=REPORT_ID, release_key=str(key))]


def c1_good_excellent(con: duckdb.DuckDBPyConnection, si: SeasonInfo) -> list[Insight]:
    out = []
    for crop in CROPS:
        cur = _latest_condition(con, crop)
        if cur is None:
            continue
        if si.state == "closed" and int(cur.season) != si.season:
            continue  # no rating in the closed season (nothing "final" to show)
        closed = si.state == "closed"
        hist = final_ratings(con, cur) if closed else condition_history(con, cur)
        vals = [float(v) for v in hist.ge_pct]
        ge = num(cur.ge_pct)
        prev_year = num(cur.nass_prev_year_ge_pct)
        params = {
            **_condition_common(cur, si),
            "ge_pct": ge,
            "good_pct": num(cur.good_pct),
            "excellent_pct": num(cur.excellent_pct),
            "nass_prev_week_ge_pct": num(cur.nass_prev_week_ge_pct),
            "nass_prev_year_ge_pct": prev_year,
            "vs_prev_year_pp": rnd(ge - prev_year, 1)
            if ge is not None and prev_year is not None
            else None,
            **range_params(ge, vals, 1),
            "history": [
                {
                    "season": int(r.season),
                    "week_ending": day(r.week_ending),
                    "ge_pct": float(r.ge_pct),
                }
                for r in hist.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"C1:{crop}",
                rule="C1",
                report_id=REPORT_ID,
                commodity_id=str(cur.commodity_id),
                kind="good_excellent",
                params=params,
                n=len(vals),
                window=WINDOW_FINAL_5Y if closed else WINDOW_OWN_5Y,
                robustness="robust",
                caveats=_caveats(crop, own_5y=True, final=closed),
                inputs=_inputs(cur),
                as_of=ts(cur.release_ts_utc),
                suppressed_reason=None if ge is not None else "no_data",
            )
        )
    return out


def c3_condition_index(con: duckdb.DuckDBPyConnection, si: SeasonInfo) -> list[Insight]:
    out = []
    for crop in CROPS:
        cur = _latest_condition(con, crop)
        if cur is None:
            continue
        hist = condition_history(con, cur)
        hist = hist[hist.ci.notna()]
        vals = [float(v) for v in hist.ci]
        ci = num(cur.ci)
        reason: Any = None
        if si.state == "closed":
            reason = "season_closed"
        elif ci is None:
            reason = "no_data"
        params = {
            **_condition_common(cur, si),
            "unit_id": "index_1_5",
            "ci": rnd(ci, 3),
            "nass_prev_year_ci": rnd(num(cur.nass_prev_year_ci), 3),
            **range_params(ci, vals, 3),
            "history": [
                {
                    "season": int(r.season),
                    "week_ending": day(r.week_ending),
                    "ci": round(float(r.ci), 3),
                }
                for r in hist.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"C3:{crop}",
                rule="C3",
                report_id=REPORT_ID,
                commodity_id=str(cur.commodity_id),
                kind="condition_index",
                params=params,
                n=len(vals),
                window=WINDOW_OWN_5Y,
                robustness="robust",
                caveats=_caveats(crop, own_5y=True),
                inputs=_inputs(cur),
                as_of=ts(cur.release_ts_utc),
                suppressed_reason=reason,
            )
        )
    return out


def pick_stage(rows: pd.DataFrame, order: list[str]) -> pd.Series:
    """The stage "in progress" this week: the latest stage (crop-calendar order) strictly
    between 0 and 100 %; else the latest stage that has started; else the first printed."""
    rank = {s: i for i, s in enumerate(order)}
    rows = rows.assign(_o=rows.category.map(lambda c: rank.get(str(c), len(order))))
    rows = rows.sort_values("_o")
    vals = rows.value_pct
    moving = rows[(vals > 0) & (vals < 100)]
    if len(moving):
        return moving.iloc[-1]
    started = rows[vals > 0]
    return started.iloc[-1] if len(started) else rows.iloc[0]


def c2_stage_pace(
    con: duckdb.DuckDBPyConnection, si: SeasonInfo, stage_order: dict[str, list[str]]
) -> list[Insight]:
    out = []
    for crop in CROPS:
        df = con.execute(
            """select * from fct_crop_progress_weekly
               where crop = ? and kind = 'progress' and week_ending =
                 (select max(week_ending) from fct_crop_progress_weekly
                  where crop = ? and kind = 'progress')""",
            [crop, crop],
        ).df()
        if df.empty:
            continue
        cur = pick_stage(df, stage_order.get(crop, []))
        value, avg = num(cur.value_pct), num(cur.nass_5yr_avg_pct)
        prev_year = num(cur.nass_prev_year_pct)
        reason: Any = None
        if si.state == "closed":
            reason = "season_closed"
        elif value is None or avg is None:
            reason = "no_data"
        rank = {c: i for i, c in enumerate(stage_order.get(crop, []))}
        stages = df.assign(_o=df.category.map(rank).fillna(99)).sort_values("_o")
        params = {
            "crop": crop,
            "season": int(cur.season),
            "week_ending": day(cur.week_ending),
            "release_key": text(cur.first_release_key) or text(cur.release_key),
            "n_states": int(cur.n_states),
            "unit_id": "pct",
            **_season_params(si),
            "stage": cur.category,
            "value_pct": value,
            "nass_5yr_avg_pct": avg,
            "avg_years": text(cur.avg_years),
            "pace_vs_5yr_pp": rnd(value - avg, 1)
            if value is not None and avg is not None
            else None,
            "nass_prev_week_pct": num(cur.nass_prev_week_pct),
            "nass_prev_year_pct": prev_year,
            "vs_prev_year_pp": rnd(value - prev_year, 1)
            if value is not None and prev_year is not None
            else None,
            "position": None
            if value is None or avg is None
            else ("behind" if value < avg else "ahead" if value > avg else "on_pace"),
            "stages": [
                {
                    "stage": r.category,
                    "value_pct": num(r.value_pct),
                    "nass_5yr_avg_pct": num(r.nass_5yr_avg_pct),
                    "nass_prev_year_pct": num(r.nass_prev_year_pct),
                }
                for r in stages.itertuples()
            ],
        }
        out.append(
            Insight(
                id=f"C2:{crop}",
                rule="C2",
                report_id=REPORT_ID,
                commodity_id=str(cur.commodity_id),
                kind="stage_pace",
                params=params,
                n=NASS_AVG_N,
                window=WINDOW_NASS_5Y,
                robustness="robust",
                caveats=_caveats(crop, own_5y=False),
                inputs=_inputs(cur),
                as_of=ts(cur.release_ts_utc),
                suppressed_reason=reason,
            )
        )
    return out
