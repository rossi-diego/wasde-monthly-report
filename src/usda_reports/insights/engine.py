"""Insights engine: run every rule on gold, apply the gates, pick cards and the hero, and
write ``insights.json`` (params only; see :mod:`usda_reports.insights.schema`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.registry import load_registry
from usda_reports.insights import gates as gates_mod
from usda_reports.insights.hero import build_hero, home_cards
from usda_reports.insights.rules import crush as crush_rules
from usda_reports.insights.rules import export_sales as es_rules
from usda_reports.insights.rules import wasde as wasde_rules
from usda_reports.insights.schema import Insight, InsightsDoc
from usda_reports.publish.focus import Focus

log = get_logger(__name__)


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "select count(*) from information_schema.tables where table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def release_index(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], datetime]:
    rows = con.execute("select report_id, release_key, release_ts_utc from dim_release").fetchall()
    return {(r, k): gates_mod.to_utc(ts) for r, k, ts in rows}


def build(
    con: duckdb.DuckDBPyConnection,
    settings: Settings,
    tag: str | None,
    now: datetime | None = None,
) -> InsightsDoc:
    now = now or datetime.now(UTC)
    registry = load_registry(settings.config_dir)
    gates = gates_mod.make_gates(registry)
    focus = Focus.load(settings.report_config_dir("wasde") / "focus.yaml")
    raw: list[Insight] = []
    screened: dict[str, int] = {}

    month, ts = wasde_rules.latest_month(con)
    w1, n_w1 = wasde_rules.w1_change_vs_prev(con, focus, month, ts)
    w2 = wasde_rules.w2_stocks_to_use_rank(con, month, ts)
    w3 = wasde_rules.w3_revision_rank(con, month, ts)
    w4 = wasde_rules.w4_brazil_soy_export_share(con, month, ts)
    raw += w1 + w2 + w3 + w4
    screened.update({"W1": n_w1, "W2": len(w2), "W3": len(w3), "W4": len(w4)})

    if _table_exists(con, "fct_export_pace"):
        pace = es_rules.pace_frame(con)
        if len(pace):
            e1 = es_rules.e1_commitment_pace(pace)
            e2 = es_rules.e2_required_weekly_sales(pace, gates.e2_min_weeks_remaining)
            e3 = es_rules.e3_china_share_soy(pace)
            raw += e1 + e2 + e3
            screened.update({"E1": len(e1), "E2": len(e2), "E3": len(e3)})

    if _table_exists(con, "fct_crush_pace"):
        crush = crush_rules.pace_frame(con)
        if len(crush):
            f1 = crush_rules.f1_crush_pace(crush)
            f2 = crush_rules.f2_required_monthly_crush(crush, gates.f2_min_months_remaining)
            f3 = crush_rules.f3_oil_yield(crush)
            raw += f1 + f2 + f3
            screened.update({"F1": len(f1), "F2": len(f2), "F3": len(f3)})

    idx = release_index(con)
    out = []
    for i in raw:
        # E2 compares with a 4-week mean and F2 with the same remaining months of last MY by
        # definition: their window, not a history sample (small_sample still applies).
        min_n = 4 if i.rule == "E2" else 1 if i.rule == "F2" else None
        out.append(gates_mod.apply(i, gates, now, idx, min_n=min_n))

    releases = [(r, k, ts.date().isoformat()) for (r, k), ts in sorted(idx.items())]
    wasde_date = idx[("wasde", month)].date().isoformat() if ("wasde", month) in idx else None
    doc = InsightsDoc(
        generated_at=now.isoformat(timespec="seconds"),
        data_tag=tag,
        gates=gates,
        n_screened=screened,
        insights=out,
        home_cards=home_cards(out),
        hero=build_hero(out, releases, wasde_date),
    )
    log.info(
        "insights.built",
        insights=len(out),
        shown=sum(1 for i in out if i.suppressed_reason is None),
        hero=doc.hero.kind,
        cards=doc.home_cards,
    )
    return doc


def write(doc: InsightsDoc, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc.model_dump(mode="json"), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def json_schema() -> dict[str, object]:
    return InsightsDoc.model_json_schema()
