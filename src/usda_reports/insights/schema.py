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
]
SuppressedReason = Literal[
    "n_below_min",  # comparison sample smaller than gates.min_n
    "stale_input",  # an input is older than cadence + grace_days
    "asof_missing",  # no point-in-time WASDE target for the ESR week
    "weeks_remaining_below_min",  # E2: fewer than gates.e2_min_weeks_remaining weeks left
    "no_data",  # the inputs needed are absent
    "first_projection",  # W3: a first projection has no revision to rank
]
Caveat = Literal[
    "small_sample",  # n < 10
    "esr_not_census",  # ESR sales/shipments differ from Census exports (WASDE)
    "unknown_may_hide_china",  # 'unknown destinations' can later be reassigned to China
    "local_marketing_years",  # BR/AR/PY use local, aggregated marketing years in WASDE
    "history_point_in_time",  # history uses the WASDE public at the time, not the final one
    "latest_only_history",  # ESR history is backfilled with revised values
    "partial_denominator",  # W4: exporters listed vary by WASDE vintage
]


class InputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    release_key: str


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 'E1:soybeans' or 'W2:corn'.")
    rule: Literal["W1", "W2", "W3", "W4", "E1", "E2", "E3"]
    report_id: Literal["wasde", "export_sales", "cross"]
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
    # Per-report staleness: cadence days + grace_days from config/reports.yaml.
    stale_after_days: dict[str, int] = Field(default_factory=dict)


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
    hero: Hero
