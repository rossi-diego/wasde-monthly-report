"""Grain Stocks silver: every bronze zip (one per quarterly release) → one long table.

Table 1 of each release (the national summary in domestic units) prints, for every grain,
the stocks on March 1, June 1, September 1 and December 1 of two years by position. Silver
keeps **every** printed value with the release that printed it (the newest date is first
printed; older dates are revised), so gold can rebuild what was public at any instant.

Row grain: release × commodity × stock date × position (``on_farm``, ``off_farm``, ``total``),
U.S. only, in thousand bushels (``k_bu``) as printed.

Envelope semantics:

* ``release_key``: the ESMIS release date (``YYYY-MM-DD``, from ``release_datetime``).
* ``release_ts_utc``: that date at the configured release time (12:00 ET) in UTC.
* ``vintage_quality``: always ``as_published``.

Other columns: ``as_of_date`` (the stock date), ``market_year`` (the marketing year in which
the stocks are held: corn/soybeans September–August, wheat June–May; September 1 corn stocks
are the ending stocks of the marketing year that just ended), ``quarter_of_my`` (1–4; 4 = the
marketing year's ending stocks), ``column_role`` (``current`` = the newest date of the release,
``earlier`` = an older, possibly revised date), ``reported_as_of`` (the newest date of the
release), ``value_flag`` (NASS symbol of a withheld value).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.manifest import Manifest, release_ts_utc
from usda_reports.core.vocab import UnseenLabelError
from usda_reports.nass_common.csv_tables import (
    NassCsvError,
    find_tables,
    normalize_title,
    parse_nass_csv,
    parse_value,
)
from usda_reports.nass_common.spec import (
    StoredRelease,
    arrow_schema,
    load_stored_releases,
    write_parquet,
)
from usda_reports.nass_common.zipfetch import NassZipError, read_member
from usda_reports.reports.grain_stocks.source import (
    REPORT_ID,
    SOURCE,
    GrainStocksError,
    SourceConfig,
)
from usda_reports.silver.envelope import ENVELOPE_COLUMNS

KEY = ["release_key", "commodity_id", "as_of_date", "position"]
SILVER_COLUMNS = [
    *ENVELOPE_COLUMNS,
    "commodity_id",
    "region_id",
    "unit_id",
    "value",
    "value_flag",
    "as_of_date",
    "position",
    "market_year",
    "my_start",
    "quarter_of_my",
    "column_role",
    "reported_as_of",
    "nass_table_id",
    "source_label",
    "source_unit_label",
    "zip_member",
    "source_url",
]
_INT = {"edition", "my_start", "quarter_of_my"}
_DATES = {"as_of_date", "reported_as_of"}
SILVER_SCHEMA = arrow_schema(SILVER_COLUMNS, ints=_INT, floats={"value"}, dates=_DATES)
# Marketing-year start month per commodity (dbt/seeds/dim_commodity.csv my_start_month).
MY_START_MONTH = {"corn": 9, "soybeans": 9, "wheat": 6}


def write_silver(df: pd.DataFrame, path: Path) -> Path:
    return write_parquet(df, SILVER_COLUMNS, SILVER_SCHEMA, path)


def market_year(commodity_id: str, as_of: date) -> tuple[str, int, int]:
    """(``2025/26``, my_start 2025, quarter_of_my 4) for corn on 2026-09-01: stocks on the
    first day of a month belong to the marketing year that contains the day before."""
    start_month = MY_START_MONTH[commodity_id]
    held = as_of - timedelta(days=1)
    start = held.year if held.month >= start_month else held.year - 1
    q = ((as_of.month - start_month) % 12) // 3
    return f"{start}/{(start + 1) % 100:02d}", start, q or 4


def parse_release(data: bytes, cfg: SourceConfig) -> pd.DataFrame:
    """Rows of table 1 of one release zip for the kept commodities (no envelope).

    Raises :class:`GrainStocksError` on a structural problem and :class:`UnseenLabelError` on
    an unknown commodity line, date label or position label."""
    try:
        member, csv_bytes = read_member(data, cfg.zip_member)
        tables = [
            t
            for t in find_tables(parse_nass_csv(csv_bytes), cfg.table.title_prefix)
            if cfg.table.must_contain in t.title
        ]
    except (NassZipError, NassCsvError) as exc:
        raise GrainStocksError(str(exc)) from exc
    if len(tables) != 1:
        raise GrainStocksError(
            f"expected one table titled {cfg.table.title_prefix!r} … {cfg.table.must_contain!r}"
            f", found {len(tables)}"
        )
    table = tables[0]
    blocks = [b for b in table.blocks if b.header_row(cfg.table.header_first_cell)]
    if len(blocks) != 1:
        raise GrainStocksError(f"table {table.number}: {len(blocks)} header blocks")
    block = blocks[0]
    labels = block.column_labels()
    # "2025 On farms" -> (2025, on_farm)
    cols: list[tuple[int, str]] = []
    for lab in labels[1:]:
        year_s, _, pos_label = lab.partition(" ")
        pos = cfg.positions.get(pos_label.strip())
        if not year_s.isdigit() or pos is None:
            raise UnseenLabelError(f"unseen Grain Stocks column {lab!r} in table {table.number}")
        cols.append((int(year_s), pos))
    units = {c.strip() for u in block.units for c in u[1:] if c.strip()}
    if not units or any(u not in cfg.units for u in units):
        raise GrainStocksError(f"table {table.number}: unit labels {sorted(units)}")
    unit_label = units.pop() if len(units) == 1 else ""
    if not unit_label:
        raise GrainStocksError(f"table {table.number}: more than one unit")
    known = set(cfg.known_groups)
    rows: list[dict[str, Any]] = []
    unseen: list[str] = []
    group: str | None = None
    for cells in block.rows:
        label = (cells[0] if cells else "").strip()
        values = cells[1:]
        if not label:
            continue
        if not any(v.strip() for v in values):
            if label in cfg.commodities:
                group = cfg.commodities[label]
            elif label in known:
                group = None
            else:
                unseen.append(label)
                group = None
            continue
        month = cfg.date_labels.get(label)
        if month is None:
            unseen.append(label)
            continue
        if group is None:
            continue
        for (year, pos), cell in zip(cols, values, strict=False):
            try:
                value, flag = parse_value(cell)
            except NassCsvError as exc:
                raise GrainStocksError(f"{group} {label} {year}: {exc}") from exc
            if value is None and flag is None:
                continue  # a date not yet published
            as_of = date(year, month, 1)
            my, my_start, q = market_year(group, as_of)
            rows.append(
                {
                    "commodity_id": group,
                    "region_id": "united_states",
                    "unit_id": cfg.units[unit_label],
                    "value": value,
                    "value_flag": flag,
                    "as_of_date": as_of,
                    "position": pos,
                    "market_year": my,
                    "my_start": my_start,
                    "quarter_of_my": q,
                    "nass_table_id": table.number,
                    "source_label": normalize_title(table.title),
                    "source_unit_label": unit_label,
                    "zip_member": member,
                }
            )
    if unseen:
        raise UnseenLabelError(
            f"unseen Grain Stocks row labels {sorted(set(unseen))}: add them to "
            "config/reports/grain_stocks/source.yaml (commodities, known_groups or date_labels)"
        )
    df = pd.DataFrame(rows)
    missing = set(cfg.commodities.values()) - (set(df.commodity_id) if len(df) else set())
    if missing:
        raise GrainStocksError(f"table {table.number}: no rows for {sorted(missing)}")
    reported = max(df.as_of_date)
    df["reported_as_of"] = reported
    df["column_role"] = ["current" if d == reported else "earlier" for d in df.as_of_date]
    return df


def check_lag(key: str, reported: date, cfg: SourceConfig) -> None:
    lag = (date.fromisoformat(key) - reported).days
    if not cfg.release_lag_days.min <= lag <= cfg.release_lag_days.max:
        raise GrainStocksError(
            f"release {key} reports stocks on {reported}: {lag} days earlier "
            f"(expected {cfg.release_lag_days.min}-{cfg.release_lag_days.max})"
        )


def build_frame(
    releases: list[StoredRelease], cfg: SourceConfig, release_time_et: str = "12:00"
) -> pd.DataFrame:
    """Silver frame (envelope first) of ``releases``; raises on any parse problem."""
    frames = []
    for r in releases:
        try:
            df = parse_release(r.data, cfg)
        except (GrainStocksError, UnseenLabelError) as exc:
            raise type(exc)(f"release {r.key}: {exc}") from exc
        check_lag(r.key, df["reported_as_of"].iloc[0], cfg)
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
    out["value"] = out["value"].astype("float64")
    return out[SILVER_COLUMNS].sort_values(KEY, kind="stable").reset_index(drop=True)


def load_releases(bronze_dir: Path, manifest: Manifest, strict: bool = True) -> list[StoredRelease]:
    return load_stored_releases(bronze_dir, manifest, REPORT_ID, GrainStocksError, strict)


def validate(silver: pd.DataFrame, contract: Contract) -> None:
    contract.enforce(silver)
    if silver.empty:
        return
    # On farms + off farms = total (± 1 thousand bushels of rounding) on every printed date.
    wide = silver.pivot_table(
        index=["release_key", "commodity_id", "as_of_date"],
        columns="position",
        values="value",
        aggfunc="first",
    ).dropna()
    if {"on_farm", "off_farm", "total"} <= set(wide.columns):
        gap = (wide["on_farm"] + wide["off_farm"] - wide["total"]).abs()
        bad = wide[gap > 1.0]
        if len(bad):
            raise ContractError(f"on farm + off farm != total: {bad.index.tolist()[:5]}")
    # A revision larger than 10% between two prints of the same date means a mis-read column.
    tot = silver[(silver.position == "total") & silver.value.notna()]
    span = tot.groupby(["commodity_id", "as_of_date"])["value"].agg(["min", "max"])
    bad_rev = span[(span["max"] - span["min"]) > 0.10 * span["max"]]
    if len(bad_rev):
        raise ContractError(f"stock revisions above 10%: {bad_rev.index.tolist()[:5]}")
