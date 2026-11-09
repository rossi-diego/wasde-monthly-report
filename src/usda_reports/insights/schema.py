"""Typed contract of ``web/public/data/insights.json`` (schema_version 1).

Python emits structured parameters only, never prose: the site renders every insight and the
hero sentence from these fields with its own i18n strings (EN / pt-BR), and a Playwright
contract test checks the rendered copy against this JSON. The JSON Schema generated from these
models is committed at ``docs/schemas/insights.schema.json`` (a test fails on drift).

Field rules (plan §6):

* ``n`` is always present (the sample behind the comparison); ``small_sample`` is in
  ``caveats`` whenever ``n < 10``; a percentile appears only when ``n >= 10``.
* A suppressed insight keeps its ``params`` for transparency but must not be shown as a
  finding; ``suppressed_reason`` says why.
* Ranks are "k of n" with an explicit ``order`` (what rank 1 means).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Literal[1] = 1

InsightKind = Literal[
    "change_vs_prev",  # W1
    "stocks_to_use_rank",  # W2
    "revision_rank",  # W3
    "brazil_soy_export_share",  # W4
    "commitment_pace",  # E1
    "required_weekly_sales",  # E2
    "china_share_soy",  # E3
    "crush_pace",  # F1
    "required_monthly_crush",  # F2
    "oil_yield",  # F3
    "good_excellent",  # C1
    "stage_pace",  # C2
    "condition_index",  # C3
    "stocks_vs_wasde",  # G1
    "implied_disappearance",  # G2
    "on_farm_share",  # G3
]
SuppressedReason = Literal[
    "n_below_min",  # comparison sample smaller than gates.min_n
    "stale_input",  # an input is older than cadence + grace_days
    "asof_missing",  # no point-in-time WASDE target for the ESR week
    "weeks_remaining_below_min",  # E2: fewer than gates.e2_min_weeks_remaining weeks left
    "months_remaining_below_min",  # F2: fewer than gates.f2_min_months_remaining months left
    "no_data",  # the inputs needed are absent
    "first_projection",  # W3: a first projection has no revision to rank
    "gap_after_cancelled_report",  # W3: Δ spans 2+ months (a WASDE was cancelled)
    "season_closed",  # C2/C3: Crop Progress season over (C1 shows the final rating instead)
]
Caveat = Literal[
    "small_sample",  # n < 10
    "esr_not_census",  # ESR sales/shipments differ from Census exports (WASDE)
    "unknown_may_hide_china",  # 'unknown destinations' can later be reassigned to China
    "local_marketing_years",  # BR/AR/PY use local, aggregated marketing years in WASDE
    "history_point_in_time",  # history uses the WASDE public at the time, not the final one
    "latest_only_history",  # ESR history is backfilled with revised values
    "partial_denominator",  # W4: exporters listed vary by WASDE vintage
    "crush_history_from_2015",  # NASS crush history starts with the 2015-10 ESMIS file
    "nass_revises_previous_month",  # each NASS release revises the previous month
    "wasde_oil_year_oct_sep",  # WASDE soybean oil year is Oct–Sep, the crush year Sep–Aug
    "nass_selected_states_aggregate",  # Crop Progress national = NASS's "<N> States" total
    "own_5yr_same_week_by_day_of_year",  # C1/C3: NASS publishes no 5-yr for condition
    "own_5yr_final_rating",  # C1 season closed: final rating vs the 5 prior final ratings
    "nass_5yr_average_as_published",  # C2: NASS's own published 5-year average
    "winter_wheat_fall_ratings_next_crop",  # fall winter-wheat ratings: next year's crop
    "grain_stocks_first_print",  # G1: NASS stocks as first printed (later revised)
    "imports_omitted_small_for_corn_soy",  # G2: imports left out of the identity
    "nass_may_revise_production_same_day",  # G2: WASDE production as of the release is used
    "nass_revises_previous_quarter",  # each Grain Stocks release revises earlier dates
]


class InputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    release_key: str


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 'E1:soybeans' or 'W2:corn'.")
    rule: Literal[
        "W1",
        "W2",
        "W3",
        "W4",
        "E1",
        "E2",
        "E3",
        "F1",
        "F2",
        "F3",
        "C1",
        "C2",
        "C3",
        "G1",
        "G2",
        "G3",
    ]
    report_id: Literal[
        "wasde", "export_sales", "oilseed_crush", "crop_progress", "grain_stocks", "cross"
    ]
    commodity_id: str | None
    kind: InsightKind
    params: dict[str, Any] = Field(description="Numbers and ids only; never prose.")
    n: int | None = Field(description="Sample size behind the comparison (always shown).")
    window: str | None = Field(
        description="Comparison window id, e.g. 'my_2010_11_to_current' or 'prior_5_my_same_week'."
    )
    robustness: Literal["robust", "fragile"]
    caveats: list[Caveat] = Field(default_factory=list)
    inputs: list[InputRef]
    as_of: str | None = Field(description="Release instant (UTC ISO) of the newest input.")
    suppressed_reason: SuppressedReason | None = None


class HeroClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["wasde_tightness", "esr_pace"]
    commodity_id: str
    direction: Literal["tighter", "looser", "lagging", "ahead", "in_line"]
    insight_ids: list[str]


class Hero(BaseModel):
    """Hero sentence as typed parameters (plan §6 'Home story selection')."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["story", "fallback"]
    clauses: list[HeroClause] = Field(default_factory=list)
    # Subline "Computed from {n_reports} reports since {since}" / fallback "{n_reports} USDA
    # reports released since {since}".
    n_reports: int
    since: str | None
    reports: list[InputRef] = Field(default_factory=list)


class Gates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_n: int = 5
    percentile_min_n: int = 10
    small_sample_below: int = 10
    e2_min_weeks_remaining: int = 6
    f2_min_months_remaining: int = 5  # = min_n: F2 compares n = months_remaining months
    # Months (1-12) in which a seasonal report's card is left off the home page (plan §6:
    # Crop Progress off-season, December to March). Its report page still shows it.
    home_hidden_months: dict[str, list[int]] = Field(
        default_factory=lambda: {"crop_progress": [12, 1, 2, 3]}
    )
    # Per-report staleness: cadence days + grace_days from config/reports.yaml.
    stale_after_days: dict[str, int] = Field(default_factory=dict)


class SeasonStatus(BaseModel):
    """Season state of a seasonal report (Crop Progress, April-November)."""

    model_config = ConfigDict(extra="forbid")

    state: Literal["in_season", "closed"]
    season: int
    latest_release_key: str
    last_scheduled: str | None
    shown_on_home: bool


class InsightsDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    generated_at: str
    data_tag: str | None
    gates: Gates
    n_screened: dict[str, int] = Field(
        description="Series screened per rule this run (multiple-comparisons note)."
    )
    insights: list[Insight]
    home_cards: list[str] = Field(description="Insight ids for the home page, in order (≤ 5).")
    seasons: dict[str, SeasonStatus] = Field(
        default_factory=dict,
        description="Season state of seasonal reports (crop_progress), for the report page.",
    )
    hero: Hero
