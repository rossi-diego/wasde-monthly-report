"""Deterministic home story selection (plan §6 'Home story selection').

* Cards (≤ 5): one per report plus at most one cross-report card, each the passing insight
  with the most extreme rank of its report. The crush card is the F1/F3 insight furthest
  outside its 5-year range (F1 on ties and when both sit inside).
* Hero clauses:
  - "tighter / looser U.S. {commodity}": W2 in the tightest / loosest third of n **and** the
    W1 ending-stocks Δ < 0 / > 0 for the same commodity; the most extreme W2 wins.
  - "sales lagging / ahead of / in line with USDA's pace": the E1 of the cross card; below the
    5-yr min → lagging, above the max → ahead, inside → in line.
  Clauses that fail their gate are dropped; with none left the hero is the neutral fallback.
"""

from __future__ import annotations

from collections.abc import Iterable

from usda_reports.insights import stats
from usda_reports.insights.schema import Hero, HeroClause, InputRef, Insight

COMMODITY_ORDER = ("soybeans", "corn", "wheat", "soybean_meal", "soybean_oil")


def _order(cid: str | None) -> int:
    return COMMODITY_ORDER.index(cid) if cid in COMMODITY_ORDER else len(COMMODITY_ORDER)


def passing(insights: Iterable[Insight]) -> list[Insight]:
    return [i for i in insights if i.suppressed_reason is None]


def _ranked(i: Insight) -> tuple[float, int, int]:
    k, n = int(i.params["k"]), int(i.n or 0)
    return (stats.extremeness(k, n), 0 if i.rule == "W2" else 1, _order(i.commodity_id))


def wasde_card(insights: list[Insight]) -> Insight | None:
    cands = [i for i in passing(insights) if i.rule in ("W2", "W3") and "k" in i.params]
    return min(cands, key=_ranked) if cands else None


def export_sales_card(insights: list[Insight]) -> Insight | None:
    ok = passing(insights)
    e3 = [i for i in ok if i.rule == "E3"]
    if e3:
        return e3[0]
    e2 = sorted((i for i in ok if i.rule == "E2"), key=lambda i: _order(i.commodity_id))
    return e2[0] if e2 else None


def crush_card(insights: list[Insight]) -> Insight | None:
    cands = [i for i in passing(insights) if i.rule in ("F1", "F3") and i.params.get("position")]
    if not cands:
        return None
    return min(cands, key=lambda i: (-float(i.params.get("outside_distance") or 0), i.rule != "F1"))


def cross_card(insights: list[Insight]) -> Insight | None:
    e1 = [i for i in passing(insights) if i.rule == "E1" and i.params.get("position")]
    if not e1:
        return None
    return min(
        e1, key=lambda i: (-float(i.params.get("outside_distance") or 0), _order(i.commodity_id))
    )


def home_cards(insights: list[Insight]) -> list[str]:
    cards = [
        wasde_card(insights),
        export_sales_card(insights),
        crush_card(insights),
        cross_card(insights),
    ]
    return [c.id for c in cards if c is not None][:5]


def wasde_clause(insights: list[Insight]) -> HeroClause | None:
    by_id = {i.id: i for i in passing(insights)}
    cands = []
    for i in by_id.values():
        if i.rule != "W2":
            continue
        w1 = by_id.get(f"W1:{i.commodity_id}:ending_stocks")
        if w1 is None or w1.params.get("delta") is None:
            continue
        delta = float(w1.params["delta"])
        if i.params["tercile"] == "tight" and delta < 0:
            cands.append((i, w1, "tighter"))
        elif i.params["tercile"] == "loose" and delta > 0:
            cands.append((i, w1, "looser"))
    if not cands:
        return None
    w2, w1, direction = min(cands, key=lambda c: _ranked(c[0]))
    assert w2.commodity_id is not None
    return HeroClause(
        kind="wasde_tightness",
        commodity_id=w2.commodity_id,
        direction=direction,
        insight_ids=[w2.id, w1.id],
    )


def esr_clause(insights: list[Insight]) -> HeroClause | None:
    card = cross_card(insights)
    if card is None:
        return None
    direction = {"below": "lagging", "above": "ahead", "inside": "in_line"}[
        str(card.params["position"])
    ]
    assert card.commodity_id is not None
    return HeroClause(
        kind="esr_pace",
        commodity_id=card.commodity_id,
        direction=direction,
        insight_ids=[card.id],
    )


def build_hero(
    insights: list[Insight], releases: list[tuple[str, str, str]], fallback_since: str | None
) -> Hero:
    """``releases``: (report_id, release_key, release date ISO) of every release in gold."""
    clauses = [c for c in (wasde_clause(insights), esr_clause(insights)) if c is not None]
    by_id = {i.id: i for i in insights}
    if clauses:
        refs = {
            (r.report_id, r.release_key)
            for c in clauses
            for iid in c.insight_ids
            for r in by_id[iid].inputs
        }
        dates = {(rid, key): d for rid, key, d in releases}
        used = sorted(refs, key=lambda r: dates.get(r, ""))
        since = min((dates[r] for r in used if r in dates), default=None)
        return Hero(
            kind="story",
            clauses=clauses,
            n_reports=len(used),
            since=since,
            reports=[InputRef(report_id=r, release_key=k) for r, k in used],
        )
    recent = [(rid, key) for rid, key, d in releases if fallback_since and d >= fallback_since]
    return Hero(
        kind="fallback",
        n_reports=len(recent),
        since=fallback_since,
        reports=[InputRef(report_id=r, release_key=k) for r, k in sorted(recent)],
    )
