"""Small, explicit statistics used by the insight rules (ranks, ranges; no z-scores)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal


def rank_low_first(current: float, others: Sequence[float]) -> tuple[int, int]:
    """Rank of ``current`` among ``others`` + itself, 1 = lowest. Ties share the better rank."""
    k = 1 + sum(1 for v in others if v < current)
    return k, len(others) + 1


def rank_high_first(current: float, others: Sequence[float]) -> tuple[int, int]:
    """Rank of ``current`` among ``others`` + itself, 1 = highest."""
    k = 1 + sum(1 for v in others if v > current)
    return k, len(others) + 1


def tercile(k: int, n: int) -> Literal["low", "middle", "high"]:
    """Which third of n ranks k falls in (k=1 is 'low')."""
    if n <= 0:
        raise ValueError("n must be positive")
    if k <= math.ceil(n / 3):
        return "low"
    if k > n - math.ceil(n / 3):
        return "high"
    return "middle"


def extremeness(k: int, n: int) -> float:
    """0 = at either end of the ranking, 0.5 = in the middle (for 'most extreme' picks)."""
    if n <= 1:
        return 0.5
    return min(k - 1, n - k) / (n - 1)


def percentile(k: int, n: int, min_n: int = 10) -> float | None:
    """Share of the other n−1 values ranked after k, in %; only when n >= min_n."""
    if n < min_n or n <= 1:
        return None
    return round(100 * (n - k) / (n - 1), 1)


def range_position(value: float, lo: float, hi: float) -> Literal["below", "inside", "above"]:
    if value < lo:
        return "below"
    if value > hi:
        return "above"
    return "inside"


def outside_distance(value: float, lo: float, hi: float) -> float:
    """How far outside [lo, hi] ``value`` is, relative to the range width (0 inside)."""
    width = max(hi - lo, 1e-9)
    if value < lo:
        return (lo - value) / width
    if value > hi:
        return (value - hi) / width
    return 0.0


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None
