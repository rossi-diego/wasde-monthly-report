"""Build the silver table from every report in the bronze manifest (full deterministic rebuild)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from wasde.config import Settings
from wasde.logs import get_logger
from wasde.manifest import Manifest
from wasde.silver.harmonize import SILVER_COLUMNS, SILVER_KEY, Vocabulary, harmonize
from wasde.silver.parse_csv import parse_csv
from wasde.silver.parse_xml import parse_xml
from wasde.silver.xml_layout import XmlLayout

log = get_logger(__name__)

# Series that must exist in every report: a cheap guard against a silently broken parse.
CORE_SERIES = [
    ("us_feed_grains_corn", "corn", "united_states", "ending_stocks"),
    ("us_soybeans_products", "soybeans", "united_states", "ending_stocks"),
    ("us_wheat", "wheat", "united_states", "ending_stocks"),
    ("world_corn", "corn", "world", "production"),
    ("world_soybeans", "soybeans", "world", "production"),
    ("world_wheat", "wheat", "world", "ending_stocks"),
]


class SilverContractError(ValueError):
    pass


def parse_report(
    month: str, path: Path, source: str, release_date: str | None, layout: XmlLayout
) -> pd.DataFrame:
    if source == "usda_csv":
        return parse_csv(path, month)
    rd = date.fromisoformat(release_date) if release_date else None
    return parse_xml(path, month, rd, layout)


def validate(silver: pd.DataFrame, min_rows: int) -> None:
    errors: list[str] = []
    for col in ["report_month", "table_id", "commodity_id", "region_id", "attribute_id", "value"]:
        n = silver[col].isna().sum()
        if n:
            errors.append(f"{n} null values in {col}")
    dups = silver.duplicated(SILVER_KEY).sum()
    if dups:
        errors.append(f"{dups} duplicate silver keys")
    counts = silver.groupby("report_month").size()
    small = counts[counts < min_rows]
    if len(small):
        errors.append(f"reports below {min_rows} rows: {small.to_dict()}")
    present = set(
        silver.loc[
            silver["period"] == "annual",
            ["report_month", "table_id", "commodity_id", "region_id", "attribute_id"],
        ]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    for month in counts.index:
        missing = [s for s in CORE_SERIES if (month, *s) not in present]
        if missing:
            errors.append(f"{month}: missing core series {missing}")
    if errors:
        raise SilverContractError("; ".join(errors[:20]))


def build_silver(settings: Settings, manifest: Manifest) -> pd.DataFrame:
    layout = XmlLayout.load(settings.config_dir / "xml_layout")
    vocab = Vocabulary.load(settings.config_dir / "mappings.yaml")
    frames = []
    for month, entry in sorted(manifest.reports.items()):
        raw = parse_report(
            month, settings.bronze_dir / entry.file, entry.source, entry.release_date, layout
        )
        if raw["release_date"].isna().all() and entry.release_date:
            raw["release_date"] = date.fromisoformat(entry.release_date)
        frames.append(raw)
    raw_all = pd.concat(frames, ignore_index=True)
    silver, unmapped = harmonize(raw_all, vocab)
    silver = silver[SILVER_COLUMNS].sort_values(
        ["commodity_id", "table_id", "region_id", "attribute_id", "market_year", "report_month"]
    )
    silver["release_date"] = pd.to_datetime(silver["release_date"]).dt.date
    validate(silver, settings.min_rows_per_report)

    settings.silver_dir.mkdir(parents=True, exist_ok=True)
    out = settings.silver_dir / "wasde.parquet"
    silver.to_parquet(out, index=False, compression="zstd")
    _write_unmapped(settings.silver_dir / "unmapped_labels.json", unmapped, raw_all, vocab)
    log.info(
        "silver.built",
        rows=len(silver),
        reports=silver["report_month"].nunique(),
        unmapped=len(unmapped),
        path=str(out),
    )
    return silver


def _write_unmapped(
    path: Path, unmapped: pd.DataFrame, raw: pd.DataFrame, vocab: Vocabulary
) -> None:
    """Record unmapped labels with the first month they appeared (drives new-label alerts)."""
    first_seen: dict[str, str] = {}
    for row in unmapped.itertuples(index=False):
        col = {"table": "report_title"}.get(row.kind, row.kind)
        months = raw.loc[raw[col] == row.label, "report_month"]
        if len(months):
            first_seen[f"{row.kind}:{row.label}"] = str(months.min())
    path.write_text(json.dumps(dict(sorted(first_seen.items())), indent=2), encoding="utf-8")


def new_labels_in(path: Path, month: str) -> list[str]:
    """Unmapped labels whose first appearance is ``month`` (i.e. introduced by that report)."""
    if not path.exists():
        return []
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return sorted(k for k, first in data.items() if first == month)
