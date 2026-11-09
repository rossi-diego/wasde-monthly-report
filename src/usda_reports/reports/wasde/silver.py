"""Build WASDE silver from every report in the bronze manifest (full deterministic rebuild)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from usda_reports.bronze.store import file_sha256
from usda_reports.core.config import Settings
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest, ReleaseEntry, release_ts_utc
from usda_reports.reports.wasde.harmonize import SILVER_COLUMNS, Vocabulary, harmonize
from usda_reports.reports.wasde.parse_csv import parse_csv
from usda_reports.reports.wasde.parse_xml import parse_xml
from usda_reports.reports.wasde.xml_layout import XmlLayout
from usda_reports.silver.envelope import add_envelope

log = get_logger(__name__)

REPORT_ID = "wasde"

SilverContractError = ContractError


def load_contract(config_dir: Path) -> Contract:
    return Contract.load(config_dir / "contracts" / f"{REPORT_ID}.yaml")


def parse_report(
    month: str, path: Path, source: str, release_date: str | None, layout: XmlLayout
) -> pd.DataFrame:
    if source == "usda_csv":
        return parse_csv(path, month)
    rd = date.fromisoformat(release_date) if release_date else None
    return parse_xml(path, month, rd, layout)


def _with_release_ts(
    releases: dict[str, ReleaseEntry], silver: pd.DataFrame, release_time_et: str
) -> dict[str, ReleaseEntry]:
    """Fill a missing release instant from the release date printed in the report itself
    (CSV files carry it; older manifest entries may not)."""
    printed = silver.groupby("report_month")["release_date"].min()
    out = {}
    for key, e in releases.items():
        if e.release_ts_utc is None and key in printed.index and pd.notna(printed[key]):
            e = e.model_copy(
                update={"release_ts_utc": release_ts_utc(printed[key], release_time_et)}
            )
        out[key] = e
    return out


def validate(
    silver: pd.DataFrame, min_rows: int | None = None, contract: Contract | None = None
) -> None:
    """Enforce the WASDE silver contract (envelope checked only when its columns exist)."""
    from usda_reports.core.config import get_settings

    c = contract or load_contract(get_settings().config_dir)
    c.enforce(silver, min_rows=min_rows, envelope="report_id" in silver.columns)


def build_silver(
    settings: Settings, manifest: Manifest, release_time_et: str = "12:00"
) -> pd.DataFrame:
    cfg = settings.report_config_dir(REPORT_ID)
    layout = XmlLayout.load(cfg / "xml_layout")
    vocab = Vocabulary.load(cfg / "mappings.yaml")
    contract = load_contract(settings.config_dir)
    releases = manifest.report(REPORT_ID).ok()
    corrupt = [
        m
        for m, e in releases.items()
        if e.file is None
        or not (settings.bronze_dir / e.file).exists()
        or file_sha256(settings.bronze_dir / e.file) != e.sha256
    ]
    if corrupt:
        raise SilverContractError(f"bronze files missing or not matching the manifest: {corrupt}")
    frames = []
    for month, entry in releases.items():
        assert entry.file is not None
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
    silver = add_envelope(
        silver, REPORT_ID, "report_month", _with_release_ts(releases, silver, release_time_et)
    )
    contract.enforce(silver, min_rows=settings.min_rows_per_report)

    settings.silver_dir.mkdir(parents=True, exist_ok=True)
    out = settings.silver_dir / f"{REPORT_ID}.parquet"
    silver.to_parquet(out, index=False, compression="zstd")
    _write_unmapped(settings.silver_dir / "unmapped_labels.json", unmapped, raw_all, vocab)
    log.info(
        "silver.built",
        report=REPORT_ID,
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
