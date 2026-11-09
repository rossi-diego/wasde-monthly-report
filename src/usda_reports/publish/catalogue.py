"""Versioned download catalogue: ``<report_id>__<dataset>__v<major>.<ext>`` (plan §7).

Parquet (zstd) is always written. CSV is plain when small, gzip-compressed otherwise.
``wasde_full.parquet`` / ``wasde_full.csv.gz`` are kept as byte-identical legacy aliases of
``wasde__values__v1`` because Soy Outlook (and other users) download them by name.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.logs import get_logger

log = get_logger(__name__)

# Column list of the legacy full dataset (= wasde__values__v1). Never reorder: the alias
# must stay byte-identical and its schema stable for downstream users.
WASDE_VALUES_COLUMNS = """
    report_month, wasde_number, release_date, source, table_id, table_label,
    commodity_id, commodity_label, region_id, region, attribute_id, attribute_label,
    reliability_stat, market_year, proj_est_flag, period, value, unit_id, unit_label
"""
# Total order: the natural key first, then every remaining column. A partial order (the key
# alone) leaves ties (reliability_stat / proj_est_flag / period variants) in thread-dependent
# order, so the Parquet bytes would differ between machines and break sha256 pins.
WASDE_VALUES_ORDER = (
    "report_month, table_id, commodity_id, region_id, attribute_id, market_year, "
    "reliability_stat, proj_est_flag, period, value, wasde_number, release_date, source, "
    "table_label, commodity_label, region, attribute_label, unit_id, unit_label"
)

# CSV above this size is gzip-compressed (keeps release assets small).
CSV_PLAIN_MAX_BYTES = 25 * 1024 * 1024
CSV_PLAIN_MAX_ROWS = 1_000_000

LEGACY_ALIASES = {
    "wasde__values__v1.parquet": "wasde_full.parquet",
    "wasde__values__v1.csv.gz": "wasde_full.csv.gz",
}


@dataclass(frozen=True)
class Dataset:
    report_id: str
    dataset: str
    major: int
    model: str
    query: str
    description: str

    @property
    def stem(self) -> str:
        return f"{self.report_id}__{self.dataset}__v{self.major}"


WASDE_DATASETS = [
    Dataset(
        "wasde",
        "values",
        1,
        "fct_wasde",
        f"select {WASDE_VALUES_COLUMNS} from fct_wasde order by {WASDE_VALUES_ORDER}",
        "Every value of every WASDE report since July 2010, harmonized (long format).",
    ),
    Dataset(
        "wasde",
        "balance_sheets",
        1,
        "fct_balance_sheet",
        "select * from fct_balance_sheet order by all",
        "Wide balance sheet per report, table, commodity, region and marketing year.",
    ),
    Dataset(
        "wasde",
        "revisions",
        1,
        "fct_revisions",
        "select * from fct_revisions order by all",
        "Revision path of every annual estimate across reports.",
    ),
    Dataset(
        "wasde",
        "changes",
        1,
        "fct_changes",
        "select * from fct_changes order by all",
        "Month-over-month revisions with seasonal materiality score and streaks.",
    ),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _gzip(src: Path, dst: Path) -> None:
    with src.open("rb") as fin, gzip.GzipFile(dst, "wb", compresslevel=6, mtime=0) as fout:
        shutil.copyfileobj(fin, fout)
    src.unlink()


def write_dataset(
    con: duckdb.DuckDBPyConnection, ds: Dataset, out_dir: Path
) -> tuple[list[Path], int]:
    """Write Parquet + CSV for one dataset; returns the files written and the row count."""
    pq = out_dir / f"{ds.stem}.parquet"
    con.execute(f"copy ({ds.query}) to '{pq.as_posix()}' (format parquet, compression zstd)")
    rows = con.execute(f"select count(*) from read_parquet('{pq.as_posix()}')").fetchone()
    n = int(rows[0]) if rows else 0
    if ds.stem == "wasde__values__v1":
        # Written exactly like the legacy wasde_full.csv.gz (which becomes its alias).
        csv = out_dir / f"{ds.stem}.csv.gz"
        con.execute(f"copy ({ds.query}) to '{csv.as_posix()}' (header, compression gzip)")
        return [pq, csv], n
    plain = out_dir / f"{ds.stem}.csv"
    con.execute(f"copy ({ds.query}) to '{plain.as_posix()}' (header)")
    if n >= CSV_PLAIN_MAX_ROWS or plain.stat().st_size > CSV_PLAIN_MAX_BYTES:
        gz = plain.with_suffix(".csv.gz")
        _gzip(plain, gz)
        return [pq, gz], n
    return [pq, plain], n


def write_catalogue(
    con: duckdb.DuckDBPyConnection, out_dir: Path, datasets: list[Dataset] | None = None
) -> list[dict[str, Any]]:
    """Write every dataset, the legacy aliases and ``datasets.json``; return its entries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for ds in datasets or WASDE_DATASETS:
        files, n = write_dataset(con, ds, out_dir)
        for path in files:
            entries.append(
                {
                    "report_id": ds.report_id,
                    "dataset": ds.dataset,
                    "schema_version": ds.major,
                    "file": path.name,
                    "format": "parquet" if path.suffix == ".parquet" else "csv",
                    "model": ds.model,
                    "rows": n,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "description": ds.description,
                }
            )
    for src, alias in LEGACY_ALIASES.items():
        if (out_dir / src).exists():
            shutil.copyfile(out_dir / src, out_dir / alias)
            entries.append(
                {
                    **next(e for e in entries if e["file"] == src),
                    "file": alias,
                    "legacy_alias_of": src,
                }
            )
    (out_dir / "datasets.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    log.info("publish.catalogue", files=len(entries), dir=str(out_dir))
    return entries
