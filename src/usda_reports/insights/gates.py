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
    """
    caveats = list(insight.caveats)
    small = insight.n is not None and insight.n < gates.small_sample_below
    if small and "small_sample" not in caveats:
        caveats.append("small_sample")
    reason = insight.suppressed_reason
    if reason is None:
        for ref in insight.inputs:
            ts = input_ts.get((ref.report_id, ref.release_key))
            limit = gates.stale_after_days.get(ref.report_id)
            if ts is None or limit is None:
                continue
            if now - ts > timedelta(days=limit):
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
