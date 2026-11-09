"""Site JSON for the commodity lenses: ``web/public/data/lens/<commodity>.json``.

One commodity, every report (plan §8 /commodities, cut line C): the latest headline numbers
of every report that covers the commodity (WASDE, Export Sales, NASS crush, Crop Progress,
Grain Stocks) from ``fct_commodity_lens``, each with its source report, release key, release
instant, period and next release, plus the ids of that commodity's insights that pass their
gates (the page renders them from insights.json). Soybeans and corn only (plan §8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.logs import get_logger
from usda_reports.core.registry import Registry
from usda_reports.insights.rules.common import day, num, text, ts
from usda_reports.insights.schema import InsightsDoc
from usda_reports.publish.web_json import _dump

log = get_logger(__name__)

SCHEMA_VERSION = 1
LENSES = {"soybeans": "Soybeans", "corn": "Corn"}
REPORT_ORDER = ("wasde", "export_sales", "oilseed_crush", "crop_progress", "grain_stocks")
SHARE_DP = 6


def lens_payload(
    con: duckdb.DuckDBPyConnection,
    commodity_id: str,
    registry: Registry,
    next_release: dict[str, str | None],
    insights: InsightsDoc | None,
) -> dict[str, Any] | None:
    df = con.execute(
        "select * from fct_commodity_lens where commodity_id = ? order by report_id, metric",
        [commodity_id],
    ).df()
    if df.empty:
        return None
    reports = []
    for rid in REPORT_ORDER:
        g = df[df.report_id == rid]
        if g.empty:
            continue
        cfg = registry.reports.get(rid)
        newest = g.sort_values("release_ts_utc").iloc[-1]
        reports.append(
            {
                "report_id": rid,
                "title": cfg.title if cfg else rid,
                "agency": cfg.agency if cfg else None,
                "release_key": text(newest.release_key),
                "release_ts_utc": ts(newest.release_ts_utc),
                "next_release": next_release.get(rid),
                "metrics": [
                    {
                        "metric": r.metric,
                        "value": num(r.value),
                        "unit_id": text(r.unit_id),
                        "period": text(r.period),
                        "period_date": day(r.period_date),
                        "market_year": text(r.market_year),
                        "release_key": text(r.release_key),
                        "release_ts_utc": ts(r.release_ts_utc),
                        "source_url": text(r.source_url),
                    }
                    for r in g.itertuples()
                ],
            }
        )
    passing = (
        [
            i.id
            for i in insights.insights
            if i.commodity_id == commodity_id and i.suppressed_reason is None
        ]
        if insights is not None
        else []
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "commodity_id": commodity_id,
        "label": LENSES.get(commodity_id, commodity_id),
        "n_reports": len(reports),
        "reports": reports,
        "insight_ids": passing,
    }


def build_commodity_lenses(
    con: duckdb.DuckDBPyConnection,
    out_dir: Path,
    registry: Registry,
    next_release: dict[str, str | None],
    insights: InsightsDoc | None,
) -> dict[str, Any] | None:
    """Write ``lens/<id>.json`` and ``lens/index.json`` (``commodities/`` holds the WASDE
    commodity JSON); None without the mart."""
    row = con.execute(
        "select count(*) from information_schema.tables where table_name = 'fct_commodity_lens'"
    ).fetchone()
    if not row or not row[0]:
        return None
    folder = out_dir / "lens"
    items = []
    for cid in LENSES:
        payload = lens_payload(con, cid, registry, next_release, insights)
        if payload is None:
            continue
        _dump(folder / f"{cid}.json", payload, nd=SHARE_DP)
        items.append(
            {
                "id": cid,
                "label": payload["label"],
                "n_reports": payload["n_reports"],
                "file": f"lens/{cid}.json",
            }
        )
    if not items:
        return None
    index = {"schema_version": SCHEMA_VERSION, "commodities": items}
    _dump(folder / "index.json", index)
    log.info("publish.commodity_lenses", commodities=[i["id"] for i in items])
    return index
