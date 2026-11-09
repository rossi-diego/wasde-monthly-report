"""Insight engine pieces: ranks, gates (n, staleness, small sample), hero selection and the
insights.json schema (plan §6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from usda_reports.core.config import PROJECT_ROOT
from usda_reports.core.registry import load_registry
from usda_reports.insights import gates, stats
from usda_reports.insights.engine import json_schema
from usda_reports.insights.hero import build_hero, home_cards
from usda_reports.insights.schema import InputRef, Insight

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def test_ranks_are_k_of_n():
    assert stats.rank_low_first(5.0, [6.0, 7.0, 4.0]) == (2, 4)
    assert stats.rank_high_first(5.0, [6.0, 7.0, 4.0]) == (3, 4)
    assert stats.rank_low_first(1.0, []) == (1, 1)
    assert stats.tercile(1, 17) == "low" and stats.tercile(9, 17) == "middle"
    assert stats.tercile(17, 17) == "high"
    assert stats.extremeness(1, 17) == 0 and stats.extremeness(9, 17) == 0.5


def test_percentile_only_from_n_10():
    assert stats.percentile(2, 9) is None
    assert stats.percentile(1, 10) == 100.0 and stats.percentile(10, 10) == 0.0


def test_range_position():
    assert stats.range_position(0.3, 0.4, 0.6) == "below"
    assert stats.range_position(0.5, 0.4, 0.6) == "inside"
    assert stats.range_position(0.7, 0.4, 0.6) == "above"
    assert stats.outside_distance(0.7, 0.4, 0.6) == pytest.approx(0.5)


def _ins(**kw) -> Insight:
    base = {
        "id": "E1:soybeans",
        "rule": "E1",
        "report_id": "cross",
        "commodity_id": "soybeans",
        "kind": "commitment_pace",
        "params": {},
        "n": 5,
        "window": "prior_5_my_same_week",
        "robustness": "robust",
        "inputs": [InputRef(report_id="export_sales", release_key="2026-11-05")],
        "as_of": None,
    }
    return Insight(**{**base, **kw})


def _gates():
    return gates.make_gates(load_registry(PROJECT_ROOT / "config"))


def test_gates_staleness_per_cadence():
    g = _gates()
    assert g.stale_after_days["export_sales"] == 17 and g.stale_after_days["wasde"] == 76
    ts = {("export_sales", "2026-11-05"): NOW - timedelta(days=4)}
    ok = gates.apply(_ins(), g, NOW, ts)
    assert ok.suppressed_reason is None and "small_sample" in ok.caveats
    old = {("export_sales", "2026-11-05"): NOW - timedelta(days=18)}
    assert gates.apply(_ins(), g, NOW, old).suppressed_reason == "stale_input"


def test_gates_sample_size_and_explicit_reasons():
    g = _gates()
    ts = {("export_sales", "2026-11-05"): NOW}
    assert gates.apply(_ins(n=4), g, NOW, ts).suppressed_reason == "n_below_min"
    assert gates.apply(_ins(n=4), g, NOW, ts, min_n=4).suppressed_reason is None
    asof = gates.apply(_ins(suppressed_reason="asof_missing"), g, NOW, ts)
    assert asof.suppressed_reason == "asof_missing"
    big = gates.apply(_ins(n=17), g, NOW, ts)
    assert "small_sample" not in big.caveats


def _w2(cid: str, k: int, tercile: str) -> Insight:
    return _ins(
        id=f"W2:{cid}",
        rule="W2",
        report_id="wasde",
        commodity_id=cid,
        kind="stocks_to_use_rank",
        params={"k": k, "tercile": tercile},
        n=17,
        inputs=[InputRef(report_id="wasde", release_key="2026-10")],
    )


def _w1(cid: str, delta: float) -> Insight:
    return _ins(
        id=f"W1:{cid}:ending_stocks",
        rule="W1",
        report_id="wasde",
        commodity_id=cid,
        kind="change_vs_prev",
        params={"delta": delta},
        n=45,
        inputs=[InputRef(report_id="wasde", release_key="2026-10")],
    )


def _e1(cid: str, position: str, dist: float) -> Insight:
    return _ins(
        id=f"E1:{cid}",
        commodity_id=cid,
        params={"position": position, "outside_distance": dist},
        inputs=[
            InputRef(report_id="export_sales", release_key="2026-11-05"),
            InputRef(report_id="wasde", release_key="2026-10"),
        ],
    )


RELEASES = [("wasde", "2026-10", "2026-10-09"), ("export_sales", "2026-11-05", "2026-11-05")]


def test_hero_tighter_needs_rank_and_falling_stocks():
    ins = [_w2("soybeans", 2, "tight"), _w1("soybeans", -20), _e1("soybeans", "below", 0.4)]
    hero = build_hero(ins, RELEASES, "2026-10-09")
    assert hero.kind == "story"
    assert [(c.kind, c.direction) for c in hero.clauses] == [
        ("wasde_tightness", "tighter"),
        ("esr_pace", "lagging"),
    ]
    assert hero.n_reports == 2 and hero.since == "2026-10-09"
    # Rising stocks contradict "tighter": that clause is dropped.
    hero2 = build_hero(
        [_w2("soybeans", 2, "tight"), _w1("soybeans", 15), _e1("corn", "inside", 0)],
        RELEASES,
        "2026-10-09",
    )
    assert [(c.kind, c.direction, c.commodity_id) for c in hero2.clauses] == [
        ("esr_pace", "in_line", "corn")
    ]


def test_hero_picks_the_e1_furthest_outside_and_falls_back():
    ins = [_e1("soybeans", "above", 0.2), _e1("corn", "below", 0.9)]
    hero = build_hero(ins, RELEASES, "2026-10-09")
    assert hero.clauses[0].commodity_id == "corn" and hero.clauses[0].direction == "lagging"
    suppressed = [i.model_copy(update={"suppressed_reason": "stale_input"}) for i in ins]
    fb = build_hero(suppressed, RELEASES, "2026-10-09")
    assert fb.kind == "fallback" and fb.clauses == [] and fb.n_reports == 2


def test_home_cards_one_per_report_plus_cross():
    e3 = _ins(
        id="E3:soybeans",
        rule="E3",
        report_id="export_sales",
        kind="china_share_soy",
        params={"china_share": 0.5},
    )
    w3 = _w2("corn", 2, "tight").model_copy(update={"id": "W3:corn", "rule": "W3"})
    ins = [_w2("soybeans", 9, "middle"), w3, e3, _e1("soybeans", "above", 0.3)]
    assert home_cards(ins) == ["W3:corn", "E3:soybeans", "E1:soybeans"]


def test_committed_json_schema_matches_models():
    committed = json.loads(
        (PROJECT_ROOT / "docs" / "schemas" / "insights.schema.json").read_text(encoding="utf-8")
    )
    assert committed == json_schema(), "run `usda-reports insights-schema` and commit"


def _w3_con(months_since_prev: int):
    import duckdb

    con = duckdb.connect()
    con.execute(
        """create table fct_balance_sheet as select * from (values
             ('2025-11', 'us_soybeans_products', 'soybeans', 'united_states', '2025/26'))
           t(report_month, table_id, commodity_id, region_id, market_year)"""
    )
    con.execute(
        """create table fct_revisions (report_month varchar, table_id varchar,
             commodity_id varchar, region_id varchar, attribute_id varchar, market_year varchar,
             my_start int, delta double, cycle_month int, series_key varchar, unit_id varchar,
             months_since_prev int)"""
    )
    rows = [("2025-11", "2025/26", 2025, -50.0, months_since_prev)]
    rows += [
        (f"{y + 1}-11", f"{y}/{(y + 1) % 100:02d}", y, float(10 + y % 7), 1)
        for y in range(2010, 2025)
    ]
    for m, my, start, d, gap in rows:
        con.execute(
            "insert into fct_revisions values (?, 'us_soybeans_products', 'soybeans',"
            " 'united_states', 'ending_stocks', ?, ?, ?, 6, 'soy_es', 'm_bu', ?)",
            [m, my, start, d, gap],
        )
    return con


def test_w3_suppressed_after_a_cancelled_wasde():
    """A Δ spanning two months (the report before it was cancelled) is not ranked against
    one-month revisions; a normal one-month Δ is ranked k of n."""
    from usda_reports.insights.rules.wasde import w3_revision_rank

    ts = "2025-11-14T17:00:00Z"
    gap = {i.id: i for i in w3_revision_rank(_w3_con(2), "2025-11", ts)}
    soy = gap["W3:soybeans"]
    assert soy.suppressed_reason == "gap_after_cancelled_report"
    assert soy.params["months_since_prev"] == 2 and soy.n is None
    ok = {i.id: i for i in w3_revision_rank(_w3_con(1), "2025-11", ts)}
    assert ok["W3:soybeans"].suppressed_reason is None
    assert (
        ok["W3:soybeans"].params["k"] == 1 and ok["W3:soybeans"].n == 16
    )  # n counts the current season
