"""Fats & Oils silver: every bronze zip (one per release) → one long table of vintages.

Each release prints the soybean table for three months (year-ago, previous month as revised,
current month; the first ESMIS release, 2015-10-01, prints four consecutive months). Silver
keeps **every** printed value with the release that printed it, so the gold layer can rebuild
what was known at any instant (point in time) and also the latest revised value per month.

Row grain: release × month × metric (``oilseed`` is constant: soybeans).

Envelope semantics:

* ``release_key``: the ESMIS release date (``YYYY-MM-DD``, from ``release_datetime``, never
  from the zip file name).
* ``release_ts_utc``: that date at the configured release time (15:00 ET) in UTC.
* ``vintage_quality``: always ``as_published`` (the zips are the files NASS released).

Other columns: ``month`` (first day of the data month), ``market_year`` (soybean crush year,
September–August, WASDE notation ``2026/27``), ``month_of_my`` (1 = September),
``column_role`` (``current`` | ``previous`` | ``year_ago`` | ``earlier``), ``reported_month``
(the newest month in that release), ``value_flag`` (NASS symbol of a withheld value).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from usda_reports.bronze.store import file_sha256
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest, release_ts_utc
from usda_reports.core.vocab import UnseenLabelError
from usda_reports.nass_common.csv_tables import (
    NassCsvError,
    find_tables,
    parse_nass_csv,
    parse_value,
)
from usda_reports.nass_common.zipfetch import NassZipError, read_member
from usda_reports.reports.oilseed_crush.source import REPORT_ID, SOURCE, NassError, SourceConfig
from usda_reports.silver.envelope import ENVELOPE_COLUMNS

log = get_logger(__name__)

KEY = ["release_key", "month", "metric"]
SILVER_COLUMNS = [
    *ENVELOPE_COLUMNS,
    "commodity_id",
    "region_id",
    "unit_id",
    "value",
    "value_flag",
    "oilseed",
    "metric",
    "month",
    "market_year",
    "my_start",
    "month_of_my",
    "column_role",
    "reported_month",
    "nass_table_id",
    "source_label",
    "source_unit_label",
    "zip_member",
    "source_url",
]
_INT = {"edition", "my_start", "month_of_my"}
_DATES = {"month", "reported_month"}
SILVER_SCHEMA = pa.schema(
    [
        (
            c,
            pa.timestamp("ns", tz="UTC")
            if c == "release_ts_utc"
            else pa.float64()
            if c == "value"
            else pa.date32()
            if c in _DATES
            else pa.int32()
            if c in _INT
            else pa.string(),
        )
        for c in SILVER_COLUMNS
    ]
)
# Marketing year of the soybean crush (dbt/seeds/dim_commodity.csv: soybeans start month 9).
MY_START_MONTH = 9

_MONTH_RE = re.compile(r"^([A-Z][a-z]+) (\d{4})$")
# Table title month: "...: September 2026 with Comparisons" or "...: May 2015 - August 2015".
_TITLE_MONTH_RE = re.compile(r":\s*(?:[A-Z][a-z]+ \d{4}\s*[-–]\s*)?([A-Z][a-z]+ \d{4})")


def write_silver(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df[SILVER_COLUMNS], schema=SILVER_SCHEMA, preserve_index=False)
    pq.write_table(table, path)
    return path


def month_label(s: str) -> date:
    """``"September 2026"`` → 2026-09-01."""
    m = _MONTH_RE.match(s.strip())
    if not m:
        raise NassError(f"unexpected month header {s!r}")
    return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %Y").date()


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def market_year(month: date, start_month: int = MY_START_MONTH) -> tuple[str, int, int]:
    """(``2026/27``, my_start 2026, month_of_my 1) for September 2026."""
    start = month.year if month.month >= start_month else month.year - 1
    return (
        f"{start}/{(start + 1) % 100:02d}",
        start,
        months_between(date(start, start_month, 1), month) + 1,
    )


def column_role(month: date, reported: date) -> str:
    lag = months_between(month, reported)
    return {0: "current", 1: "previous", 12: "year_ago"}.get(lag, "earlier")


def title_month(title: str) -> date:
    """Newest month named in the table title."""
    m = _TITLE_MONTH_RE.search(title)
    if not m:
        raise NassError(f"no month in table title {title!r}")
    return month_label(m.group(1))


def parse_release(data: bytes, cfg: SourceConfig, release_key: str | None = None) -> pd.DataFrame:
    """Rows of the soybean table of one release zip (no envelope).

    Raises :class:`NassError` on a structural problem and :class:`UnseenLabelError` on a row
    label that is neither a configured metric nor a known non-metric row. Month headers must
    be in order and end at the month named in the title; known header typos are corrected
    from ``header_fixes`` (per release key)."""
    try:
        member, csv_bytes = read_member(data, cfg.zip_member)
        tables = find_tables(parse_nass_csv(csv_bytes), cfg.table.title_prefix)
    except (NassZipError, NassCsvError) as exc:
        raise NassError(str(exc)) from exc
    if len(tables) != 1:
        raise NassError(
            f"expected one table titled {cfg.table.title_prefix!r}, found {len(tables)}"
        )
    table = tables[0]
    if table.number != cfg.table.number:
        raise NassError(f"soybean table is number {table.number}, expected {cfg.table.number}")
    header = next(
        (h for b in table.blocks if (h := b.header_row(cfg.table.header_first_cell))), None
    )
    if header is None:
        raise NassError(f"table {table.number}: no header row starting with 'Item'")
    fixes = cfg.header_fixes.get(release_key or "", {})
    month_cells = [fixes.get(c.strip(), c.strip()) for c in header[2:] if c.strip()]
    months = [month_label(c) for c in month_cells]
    if not months or months != sorted(months) or len(set(months)) != len(months):
        raise NassError(f"table {table.number}: month columns {month_cells} not in order")
    reported = max(months)
    if reported != title_month(table.title):
        raise NassError(
            f"table {table.number}: newest column {reported:%B %Y} differs from the title "
            f"{table.title!r}"
        )
    known = {k.strip() for k in cfg.known_rows}
    rows: list[dict[str, Any]] = []
    unseen: list[str] = []
    seen_metrics: set[str] = set()
    for block in table.blocks:
        for cells in block.rows:
            label = (cells[0] if cells else "").strip()
            if not label:
                continue
            ref = cfg.metrics.get(label)
            if ref is None:
                if label not in known:
                    unseen.append(label)
                continue
            if ref.metric in seen_metrics:
                raise NassError(f"table {table.number}: row {label!r} printed twice")
            seen_metrics.add(ref.metric)
            unit_label = cells[1].strip() if len(cells) > 1 else ""
            unit = cfg.units.get(unit_label)
            if unit != ref.unit:
                raise NassError(
                    f"table {table.number}: {label!r} unit {unit_label!r} (expected {ref.unit})"
                )
            values = cells[2 : 2 + len(months)]
            if len(values) != len(months):
                raise NassError(f"table {table.number}: {label!r} has {len(values)} values")
            for mon, cell in zip(months, values, strict=True):
                try:
                    value, flag = parse_value(cell)
                except NassCsvError as exc:
                    raise NassError(f"{label!r} {mon:%Y-%m}: {exc}") from exc
                my, my_start, month_of_my = market_year(mon)
                rows.append(
                    {
                        "commodity_id": ref.commodity_id,
                        "region_id": "united_states",
                        "unit_id": unit,
                        "value": value,
                        "value_flag": flag,
                        "oilseed": cfg.oilseed,
                        "metric": ref.metric,
                        "month": mon,
                        "market_year": my,
                        "my_start": my_start,
                        "month_of_my": month_of_my,
                        "column_role": column_role(mon, reported),
                        "reported_month": reported,
                        "nass_table_id": table.number,
                        "source_label": label,
                        "source_unit_label": unit_label,
                        "zip_member": member,
                    }
                )
    if unseen:
        raise UnseenLabelError(
            f"unseen Fats & Oils row labels {sorted(set(unseen))}: add them to "
            "config/reports/oilseed_crush/source.yaml (metrics or known_rows)"
        )
    missing = {m.metric for m in cfg.metrics.values()} - seen_metrics
    if missing:
        raise NassError(f"table {table.number}: rows missing for {sorted(missing)}")
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class StoredRelease:
    key: str
    sha256: str
    edition: int
    url: str | None
    data: bytes


def check_lag(key: str, reported: date, cfg: SourceConfig) -> None:
    lag = months_between(reported, date.fromisoformat(key))
    if not cfg.lag_months.min <= lag <= cfg.lag_months.max:
        raise NassError(
            f"release {key} reports {reported:%B %Y}: {lag} months earlier "
            f"(expected {cfg.lag_months.min}-{cfg.lag_months.max})"
        )


def build_frame(
    releases: list[StoredRelease], cfg: SourceConfig, release_time_et: str = "15:00"
) -> pd.DataFrame:
    """Silver frame (envelope first) of ``releases``; raises on any parse problem."""
    frames = []
    for r in releases:
        df = parse_release(r.data, cfg, r.key)
        check_lag(r.key, df["reported_month"].iloc[0], cfg)
        ts = release_ts_utc(r.key, release_time_et)
        df.insert(0, "report_id", REPORT_ID)
        df.insert(1, "release_key", r.key)
        df.insert(2, "release_ts_utc", pd.Timestamp(ts))
        df.insert(3, "edition", r.edition)
        df.insert(4, "source", SOURCE)
        df.insert(5, "bronze_sha256", r.sha256)
        df.insert(6, "vintage_quality", "as_published")
        df["source_url"] = r.url
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=SILVER_COLUMNS)
    out = pd.concat(frames, ignore_index=True)
    out["release_ts_utc"] = pd.to_datetime(out["release_ts_utc"], utc=True)
    for c in _INT:
        out[c] = out[c].astype("int32")
    return out[SILVER_COLUMNS].sort_values(KEY, kind="stable").reset_index(drop=True)


def load_releases(bronze_dir: Path, manifest: Manifest, strict: bool = True) -> list[StoredRelease]:
    """Every ok crush bronze entry in release order, sha256-verified.

    ``strict=False`` (the last-good fallback) stops at the first missing or altered file and
    returns the verified releases before it."""
    out = []
    for key, e in manifest.report(REPORT_ID).ok().items():
        assert e.file is not None
        path = bronze_dir / e.file
        if not path.exists() or file_sha256(path) != e.sha256:
            if not strict:
                log.error("silver.oilseed_crush_bad_bronze", file=e.file)
                break
            raise NassError(f"bronze {e.file}: missing or sha256 mismatch")
        out.append(
            StoredRelease(
                key=key, sha256=str(e.sha256), edition=e.edition, url=e.url, data=path.read_bytes()
            )
        )
    return out


def validate(silver: pd.DataFrame, contract: Contract) -> None:
    contract.enforce(silver)
    if silver.empty:
        return
    # Each month's newest vintage must not jump between releases by more than a revision
    # would (a mis-read column would): the current-month value must match how the next
    # release prints it as the previous month within 15%.
    crushed = silver[silver.metric == "crushed_st"]
    cur = crushed[crushed.column_role == "current"].set_index("month")["value"]
    prev = crushed[crushed.column_role == "previous"].set_index("month")["value"]
    both = cur.to_frame("cur").join(prev.to_frame("prev"), how="inner").dropna()
    bad = both[(both.prev - both.cur).abs() > 0.15 * both.cur]
    if len(bad):
        raise ContractError(f"crush revisions above 15% for months {list(bad.index)[:5]}")
