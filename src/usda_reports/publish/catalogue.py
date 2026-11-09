"""Versioned download catalogue: ``<report_id>__<dataset>__v<major>.<ext>`` (plan §7).

Datasets are declared in ``config/datasets.yaml`` (model → file name → schema version →
formats). Parquet (zstd) is always written. CSV is plain when small, gzip-compressed
otherwise. ``wasde_full.parquet`` / ``wasde_full.csv.gz`` are kept as byte-identical legacy
aliases of ``wasde__values__v1`` because Soy Outlook (and other users) download them by name.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

from usda_reports.core.config import PROJECT_ROOT
from usda_reports.core.logs import get_logger

log = get_logger(__name__)

# Column list of the legacy full dataset (= wasde__values__v1). Never reorder: the alias
# must stay byte-identical and its schema stable for downstream users. config/datasets.yaml
# must agree (tests/integration/test_soy_outlook_compat.py checks it).
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
# Parquet files up to this size are also served from the site (web/public/data/downloads).
SITE_PREVIEW_MAX_BYTES = 5 * 1024 * 1024

# The installed (non-editable) package, e.g. in Docker, finds config through USDA_CONFIG_DIR.
DATASETS_YAML = Path(os.environ.get("USDA_CONFIG_DIR") or PROJECT_ROOT / "config") / "datasets.yaml"


@dataclass(frozen=True)
class Dataset:
    report_id: str
    dataset: str
    major: int
    model: str
    query: str
    description: str
    csv_gzip: bool = False
    coverage: str | None = None
    release_column: str | None = None
    site_preview: bool = False
    aliases: dict[str, str] = field(default_factory=dict)
    licence: str | None = None  # cross datasets name every agency they combine

    @property
    def stem(self) -> str:
        return f"{self.report_id}__{self.dataset}__v{self.major}"


def load_datasets(path: Path = DATASETS_YAML) -> list[Dataset]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for d in raw["datasets"]:
        cols = d.get("columns", "*")
        select = "*" if cols == "*" else ", ".join(cols)
        order = " ".join(str(d.get("order_by", "all")).split())
        out.append(
            Dataset(
                report_id=d["report_id"],
                dataset=d["dataset"],
                major=int(d["schema_version"]),
                model=d["model"],
                query=f"select {select} from {d['model']} order by {order}",
                description=" ".join(str(d["description"]).split()),
                csv_gzip=bool(d.get("csv_gzip", False)),
                coverage=d.get("coverage"),
                release_column=d.get("release_column"),
                site_preview=bool(d.get("site_preview", False)),
                aliases=dict(d.get("aliases") or {}),
                licence=d.get("licence"),
            )
        )
    return out


ALL_DATASETS = load_datasets()
WASDE_DATASETS = [d for d in ALL_DATASETS if d.report_id == "wasde"]
LEGACY_ALIASES = {
    f"{d.stem}.{'parquet' if fmt == 'parquet' else 'csv.gz'}": alias
    for d in ALL_DATASETS
    for fmt, alias in d.aliases.items()
}


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
    if ds.csv_gzip:
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


def _table_rows(con: duckdb.DuckDBPyConnection, model: str) -> int | None:
    exists = con.execute(
        "select count(*) from information_schema.tables where table_name = ?", [model]
    ).fetchone()
    if not exists or not exists[0]:
        return None
    row = con.execute(f"select count(*) from {model}").fetchone()
    return int(row[0]) if row else 0


def _span(con: duckdb.DuckDBPyConnection, ds: Dataset) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if ds.coverage:
        lo, hi = con.execute(
            f"select min({ds.coverage})::varchar, max({ds.coverage})::varchar from {ds.model}"
        ).fetchone() or (None, None)
        out["coverage"] = {"start": lo, "end": hi}
    if ds.release_column:
        row = con.execute(f"select max({ds.release_column})::varchar from {ds.model}").fetchone()
        out["latest_release_key"] = row[0] if row else None
    return out


def write_catalogue(
    con: duckdb.DuckDBPyConnection, out_dir: Path, datasets: list[Dataset] | None = None
) -> list[dict[str, Any]]:
    """Write every dataset, the legacy aliases and ``datasets.json``; return its entries.

    A non-WASDE dataset whose model is missing or empty (a report that failed or was never
    ingested) is skipped, so one report cannot block the others.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    with utc_session(con):
        return _write_catalogue(con, out_dir, datasets)


@contextmanager
def utc_session(con: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """Render TIMESTAMPTZ in UTC for the duration of the export.

    DuckDB prints ``*_ts_utc`` columns (CSV text, ``::varchar`` spans) in the session time zone,
    which defaults to the machine's: a Brazilian laptop wrote ``2015-10-01 16:00:00-03`` where
    CI wrote ``2015-10-01 19:00:00+00``. Pinning UTC makes the CSV bytes, their sha256 and
    ``datasets.json`` identical on every machine. The previous setting is restored afterwards.
    """
    row = con.execute("select current_setting('TimeZone')").fetchone()
    previous = str(row[0]) if row and row[0] else None
    con.execute("set TimeZone = 'UTC'")
    try:
        yield
    finally:
        if previous is not None:
            safe = previous.replace("'", "")
            con.execute(f"set TimeZone = '{safe}'")


def _write_catalogue(
    con: duckdb.DuckDBPyConnection, out_dir: Path, datasets: list[Dataset] | None
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for ds in datasets if datasets is not None else WASDE_DATASETS:
        if ds.report_id != "wasde" and not _table_rows(con, ds.model):
            log.warning("publish.dataset_skipped", dataset=ds.stem, reason="no rows")
            continue
        files, n = write_dataset(con, ds, out_dir)
        span = _span(con, ds)
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
                    **span,
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


def dataset_by_stem(stem: str) -> Dataset:
    return next(d for d in ALL_DATASETS if d.stem == stem)
