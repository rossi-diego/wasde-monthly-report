"""Small helpers shared by the NASS insight rules (Crop Progress, Grain Stocks)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from usda_reports.insights import stats


def num(v: Any) -> float | None:
    """A float, or None for NULL / NaN."""
    return None if v is None or pd.isna(v) else float(v)


def rnd(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def ts(v: Any) -> str | None:
    """UTC ISO instant (``2026-11-02T21:00:00Z``) or None."""
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def day(v: Any) -> str | None:
    return None if v is None or pd.isna(v) else str(pd.Timestamp(v).date())


def text(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def range_params(
    value: float | None, vals: list[float], nd: int, *, high_first: bool = True
) -> dict[str, Any]:
    """5-year comparison block: mean / min / max of ``vals``, where ``value`` sits (below,
    inside, above the min–max range), how far outside (relative to the range width) and its
    rank "k of n" among ``vals`` + itself (1 = highest unless ``high_first`` is False)."""
    out: dict[str, Any] = {
        "hist_mean": None,
        "hist_min": None,
        "hist_max": None,
        "position": None,
        "outside_distance": None,
        "k": None,
        "order": "highest_first" if high_first else "lowest_first",
    }
    if not vals:
        return out
    lo, hi = min(vals), max(vals)
    out.update(hist_mean=rnd(stats.mean(vals), nd), hist_min=rnd(lo, nd), hist_max=rnd(hi, nd))
    if value is not None:
        out["position"] = stats.range_position(value, lo, hi)
        out["outside_distance"] = round(stats.outside_distance(value, lo, hi), max(nd, 4))
        rank = stats.rank_high_first if high_first else stats.rank_low_first
        out["k"] = rank(value, vals)[0]
    return out
