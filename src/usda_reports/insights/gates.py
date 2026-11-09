"""Suppression gates shared by every insight (plan §6 'Rules that apply to every insight')."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from usda_reports.core.registry import Registry
from usda_reports.insights.schema import Gates, Insight

CADENCE_DAYS = {"weekly": 7, "monthly": 31, "quarterly": 92}


def make_gates(registry: Registry) -> Gates:
    """Staleness per report = cadence + grace_days (config/reports.yaml)."""
    return Gates(
        stale_after_days={
            r.id: CADENCE_DAYS[r.cadence] + r.grace_days for r in registry.reports.values()
        }
    )


def apply(
    insight: Insight,
    gates: Gates,
    now: datetime,
    input_ts: dict[tuple[str, str], datetime],
    min_n: int | None = None,
) -> Insight:
    """Set ``suppressed_reason`` (first failing gate wins) and the ``small_sample`` caveat.

    Order: an explicit rule-level reason (no_data, asof_missing, …) is kept; then stale
    inputs; then sample size. ``min_n=None`` uses ``gates.min_n``; rules whose comparison
    window is fixed by definition (E2: 4 weeks) pass their own minimum.

    A seasonal report after its season (``params.season_state == "closed"``, Crop Progress
    December to March) is not stale: its final release is the newest data there is, shown
    as "season closed" (plan §6), so the staleness gate does not apply to it.

    The insight's own report (e.g. ``grain_stocks`` for G1) is measured against ``now``. A
    point-in-time input from another report (the WASDE public at that release) is measured
    against the own report's release instant: it must not have been stale *then*. Otherwise a
    quarterly Grain Stocks insight would go stale with its as-of WASDE after 76 days although
    the quarterly report itself is current for 192. Cross insights (``report_id = cross``)
    have no own report: every input is measured against ``now``.
    """
    caveats = list(insight.caveats)
    small = insight.n is not None and insight.n < gates.small_sample_below
    if small and "small_sample" not in caveats:
        caveats.append("small_sample")
    reason = insight.suppressed_reason
    season_closed = insight.params.get("season_state") == "closed"
    own_ts = next(
        (
            input_ts.get((r.report_id, r.release_key))
            for r in insight.inputs
            if r.report_id == insight.report_id
        ),
        None,
    )
    if reason is None and not season_closed:
        for ref in insight.inputs:
            ts = input_ts.get((ref.report_id, ref.release_key))
            limit = gates.stale_after_days.get(ref.report_id)
            if ts is None or limit is None:
                continue
            ref_time = now if ref.report_id == insight.report_id or own_ts is None else own_ts
            if ref_time - ts > timedelta(days=limit):
                reason = "stale_input"
                break
    if reason is None:
        need = gates.min_n if min_n is None else min_n
        if insight.n is None or insight.n < need:
            reason = "n_below_min"
    return insight.model_copy(update={"caveats": caveats, "suppressed_reason": reason})


def to_utc(ts: object) -> datetime:
    out = pd.Timestamp(ts)
    if out.tzinfo is None:
        out = out.tz_localize("UTC")
    return out.tz_convert("UTC").to_pydatetime()
