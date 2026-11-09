"""Crop Progress silver: every bronze zip (one per weekly release) → one long table.

Only the national row of each table is kept (NASS's "<N> States" aggregate, e.g. "18 States"),
for corn, soybeans, winter wheat and spring wheat:

* ``kind = progress``: one row per crop × stage (``planted``, ``silking``, ``harvested``…):
  ``value`` is the cumulative % of acreage this week; ``nass_prev_week_pct``,
  ``nass_prev_year_pct`` and ``nass_5yr_avg_pct`` are NASS's own published columns (the
  5-year average is used exactly as published, plan §6 C2).
* ``kind = condition``: one row per crop × rating (``very_poor`` … ``excellent``): ``value``
  is the % of acreage this week; ``nass_prev_week_pct`` / ``nass_prev_year_pct`` come from
  the "Previous week" / "Previous year" rows. NASS publishes no 5-year average for condition
  (``nass_5yr_avg_pct`` is null; gold computes its own, plan §6 C1/C3).

Envelope semantics:

* ``release_key``: the ESMIS release date (``YYYY-MM-DD``, from ``release_datetime``, never
  from the zip file name).
* ``release_ts_utc``: that date at the configured release time (16:00 ET) in UTC.
* ``vintage_quality``: always ``as_published``.

Other columns: ``week_ending`` (the Sunday the data refers to), ``season`` (its calendar
year; NASS's crop-progress season runs April-November), ``n_states``, ``value_flag`` (NASS
symbol of a missing value, e.g. ``NA``), ``prev_year_week_ending`` and ``avg_years`` (the
years behind NASS's 5-year average, e.g. ``2021-2025``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.manifest import Manifest, release_ts_utc
from usda_reports.core.vocab import UnseenLabelError
from usda_reports.nass_common.csv_tables import (
    NassBlock,
    NassCsvError,
    NassTable,
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
from usda_reports.reports.crop_progress.source import (
    REPORT_ID,
    SOURCE,
    CropProgressError,
    SourceConfig,
)
from usda_reports.silver.envelope import ENVELOPE_COLUMNS

KEY = ["release_key", "crop", "kind", "category"]
SILVER_COLUMNS = [
    *ENVELOPE_COLUMNS,
    "commodity_id",
    "region_id",
    "unit_id",
    "value",
    "value_flag",
    "crop",
    "kind",
    "category",
    "week_ending",
    "season",
    "state_id",
    "n_states",
    "nass_prev_week_pct",
    "nass_prev_year_pct",
    "nass_5yr_avg_pct",
    "prev_year_week_ending",
    "avg_years",
    "nass_table_id",
    "source_label",
    "zip_member",
    "source_url",
]
_INT = {"edition", "season", "n_states"}
_FLOAT = {"value", "nass_prev_week_pct", "nass_prev_year_pct", "nass_5yr_avg_pct"}
_DATES = {"week_ending", "prev_year_week_ending"}
SILVER_SCHEMA = arrow_schema(SILVER_COLUMNS, ints=_INT, floats=_FLOAT, dates=_DATES)

STATE_ID = "us_total"  # NASS "<N> States" aggregate (national level)
_TITLE_RE = re.compile(r"^(?P<what>.+?) - Selected States(?:: Week Ending (?P<we>.+))?$", re.I)
_WEEK_RE = re.compile(r"week ending ([A-Z][a-z]+\.? \d{1,2}),? (\d{4})", re.I)
_AVG_RE = re.compile(r"^(\d{4})-(\d{4}) Average$", re.I)


def write_silver(df: pd.DataFrame, path: Path) -> Path:
    return write_parquet(df, SILVER_COLUMNS, SILVER_SCHEMA, path)


def parse_date(text: str) -> date:
    """``"November 1, 2026"`` (or ``"Sept. 7, 2014"``) → 2026-11-01."""
    s = re.sub(r"\s+", " ", text.replace(".", "")).strip().rstrip(",")
    s = re.sub(r"^Sept ", "Sep ", s)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise CropProgressError(f"unparseable date {text!r}")


@dataclass(frozen=True)
class TableKind:
    crop: str
    kind: str  # progress | condition
    category: str | None  # stage (progress) or None (condition: one row per rating)
    week_ending: date | None  # from the title (condition tables)


def classify(title: str, cfg: SourceConfig) -> TableKind | None:
    """What a table holds, or None when it is not about a kept crop.

    A title that names a kept crop but an unknown stage raises :class:`UnseenLabelError`."""
    t = normalize_title(title)
    for crop, ref in cfg.crops.items():
        for name in sorted(ref.title_names, key=len, reverse=True):
            if not t.startswith(name + " "):
                continue
            m = _TITLE_RE.match(t[len(name) + 1 :])
            if m is None:
                raise UnseenLabelError(f"unseen Crop Progress title {title!r}")
            what = m.group("what").strip()
            we = parse_date(m.group("we")) if m.group("we") else None
            if what == cfg.condition_word:
                return TableKind(crop, "condition", None, we)
            stage = cfg.stages[crop].get(what)
            if stage is None:
                raise UnseenLabelError(
                    f"unseen Crop Progress stage {what!r} in {title!r}: add it to "
                    "config/reports/crop_progress/source.yaml (stages)"
                )
            return TableKind(crop, "progress", stage, we)
    return None


def _total_row(table: NassTable, pattern: re.Pattern[str]) -> tuple[NassBlock, int, int]:
    """(block, row index, n_states) of the single national row of a table."""
    hits = []
    for block in table.blocks:
        for i, cells in enumerate(block.rows):
            m = pattern.match((cells[0] if cells else "").strip())
            if m:
                hits.append((block, i, int(m.group(1))))
    if len(hits) != 1:
        raise CropProgressError(
            f"table {table.number} {table.title!r}: {len(hits)} national rows (expected 1)"
        )
    return hits[0]


def _check_units(table: NassTable, block: NassBlock, cfg: SourceConfig) -> None:
    allowed = {u.lower() for u in cfg.unit_labels}
    for u in block.units:
        bad = [c for c in u[1:] if c.strip() and c.strip().lower() not in allowed]
        if bad:
            raise CropProgressError(f"table {table.number}: unexpected unit labels {bad}")


def _value(cell: str, where: str) -> tuple[float | None, str | None]:
    try:
        value, flag = parse_value(cell)
    except NassCsvError as exc:
        raise CropProgressError(f"{where}: {exc}") from exc
    if value is not None and not 0 <= value <= 100:
        raise CropProgressError(f"{where}: {value} is not a percentage")
    return value, flag


def _progress_rows(
    table: NassTable, tk: TableKind, cfg: SourceConfig, pattern: re.Pattern[str]
) -> tuple[date, list[dict[str, Any]]]:
    block, i, n_states = _total_row(table, pattern)
    _check_units(table, block, cfg)
    labels = block.column_labels()[1:]
    weeks: dict[int, date] = {}
    avg_col: int | None = None
    avg_years: str | None = None
    for j, lab in enumerate(labels):
        m = _WEEK_RE.search(lab)
        if m:
            weeks[j] = parse_date(f"{m.group(1)}, {m.group(2)}")
            continue
        a = _AVG_RE.match(lab)
        if a:
            avg_col, avg_years = j, f"{a.group(1)}-{a.group(2)}"
    if len(weeks) != 3 or avg_col is None:
        raise CropProgressError(f"table {table.number} {table.title!r}: header {labels}")
    this_week = max(weeks.values())
    role: dict[str, int] = {}
    for j, d in weeks.items():
        if d == this_week:
            role["value"] = j
        elif d == this_week - timedelta(days=7):
            role["prev_week"] = j
        elif (
            d.year == this_week.year - 1
            and abs((d.replace(year=this_week.year) - this_week).days) <= 7
        ):
            role["prev_year"] = j
    if len(role) != 3:
        raise CropProgressError(
            f"table {table.number} {table.title!r}: week columns {sorted(weeks.values())}"
        )
    cells = block.rows[i][1:]
    if len(cells) < len(labels):
        raise CropProgressError(f"table {table.number}: national row has {len(cells)} values")
    where = f"{tk.crop} {tk.category}"
    value, flag = _value(cells[role["value"]], where)
    prev_week, _ = _value(cells[role["prev_week"]], where)
    prev_year, _ = _value(cells[role["prev_year"]], where)
    avg, _ = _value(cells[avg_col], where)
    prev_year_week = weeks[role["prev_year"]]
    return this_week, [
        {
            "crop": tk.crop,
            "kind": "progress",
            "category": tk.category,
            "value": value,
            "value_flag": flag,
            "n_states": n_states,
            "nass_prev_week_pct": prev_week,
            "nass_prev_year_pct": prev_year,
            "nass_5yr_avg_pct": avg,
            "prev_year_week_ending": prev_year_week,
            "avg_years": avg_years,
            "nass_table_id": table.number,
            "source_label": normalize_title(table.title),
        }
    ]


def _condition_rows(
    table: NassTable, tk: TableKind, cfg: SourceConfig, pattern: re.Pattern[str]
) -> tuple[date, list[dict[str, Any]]]:
    if tk.week_ending is None:
        raise CropProgressError(f"table {table.number} {table.title!r}: no week in the title")
    block, i, n_states = _total_row(table, pattern)
    _check_units(table, block, cfg)
    labels = block.column_labels()[1:]
    cols: dict[str, int] = {}
    for j, lab in enumerate(labels):
        cat = cfg.conditions.get(lab)
        if cat is None and lab:
            raise UnseenLabelError(f"unseen Crop Progress condition column {lab!r}")
        if cat is not None:
            cols[cat] = j
    if set(cols) != set(cfg.conditions.values()):
        raise CropProgressError(f"table {table.number}: condition columns {labels}")
    extra: dict[str, list[str]] = {}
    for cells in block.rows[i + 1 :]:
        lab = (cells[0] if cells else "").strip()
        if lab in cfg.condition_rows:
            extra[cfg.condition_rows[lab]] = cells[1:]
    if set(extra) != set(cfg.condition_rows.values()):
        raise CropProgressError(f"table {table.number}: rows {sorted(extra)} under the total")
    cur = block.rows[i][1:]
    rows = []
    for cat, j in cols.items():
        where = f"{tk.crop} condition {cat}"
        value, flag = _value(cur[j], where)
        prev_week, _ = _value(extra["prev_week"][j], where)
        prev_year, _ = _value(extra["prev_year"][j], where)
        rows.append(
            {
                "crop": tk.crop,
                "kind": "condition",
                "category": cat,
                "value": value,
                "value_flag": flag,
                "n_states": n_states,
                "nass_prev_week_pct": prev_week,
                "nass_prev_year_pct": prev_year,
                "nass_5yr_avg_pct": None,
                "prev_year_week_ending": None,
                "avg_years": None,
                "nass_table_id": table.number,
                "source_label": normalize_title(table.title),
            }
        )
    return tk.week_ending, rows


def parse_release(data: bytes, cfg: SourceConfig) -> pd.DataFrame:
    """National rows of the kept crops in one release zip (no envelope).

    Raises :class:`CropProgressError` on a structural problem (header, units, two national
    rows, mixed weeks) and :class:`UnseenLabelError` on an unknown stage or condition label."""
    try:
        member, csv_bytes = read_member(data, cfg.zip_member)
        tables = parse_nass_csv(csv_bytes)
    except (NassZipError, NassCsvError) as exc:
        raise CropProgressError(str(exc)) from exc
    pattern = re.compile(cfg.total_row_pattern)
    rows: list[dict[str, Any]] = []
    weeks: set[date] = set()
    seen: set[tuple[str, str, str | None]] = set()
    for table in tables:
        tk = classify(table.title, cfg)
        if tk is None:
            continue
        ident = (tk.crop, tk.kind, tk.category)
        if ident in seen:
            raise CropProgressError(f"{tk.crop} {tk.kind} {tk.category or ''} printed twice")
        seen.add(ident)
        if tk.kind == "progress":
            week, out = _progress_rows(table, tk, cfg, pattern)
        else:
            week, out = _condition_rows(table, tk, cfg, pattern)
        weeks.add(week)
        rows += out
    if not rows:
        raise CropProgressError("no corn, soybean or wheat table in the release")
    if len(weeks) != 1:
        raise CropProgressError(f"tables refer to different weeks {sorted(weeks)}")
    week_ending = weeks.pop()
    df = pd.DataFrame(rows)
    df["commodity_id"] = df["crop"].map({c: r.commodity_id for c, r in cfg.crops.items()})
    df["region_id"] = "united_states"
    df["unit_id"] = "pct"
    df["state_id"] = STATE_ID
    df["week_ending"] = week_ending
    df["season"] = week_ending.year
    df["zip_member"] = member
    return df


def check_lag(key: str, week_ending: date, cfg: SourceConfig) -> None:
    lag = (date.fromisoformat(key) - week_ending).days
    if not cfg.release_lag_days.min <= lag <= cfg.release_lag_days.max:
        raise CropProgressError(
            f"release {key} reports the week ending {week_ending}: {lag} days earlier "
            f"(expected {cfg.release_lag_days.min}-{cfg.release_lag_days.max})"
        )


def build_frame(
    releases: list[StoredRelease], cfg: SourceConfig, release_time_et: str = "16:00"
) -> pd.DataFrame:
    """Silver frame (envelope first) of ``releases``; raises on any parse problem."""
    frames = []
    for r in releases:
        try:
            df = parse_release(r.data, cfg)
        except (CropProgressError, UnseenLabelError) as exc:
            raise type(exc)(f"release {r.key}: {exc}") from exc
        check_lag(r.key, df["week_ending"].iloc[0], cfg)
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
    for c in _FLOAT:
        out[c] = out[c].astype("float64")
    return out[SILVER_COLUMNS].sort_values(KEY, kind="stable").reset_index(drop=True)


def load_releases(bronze_dir: Path, manifest: Manifest, strict: bool = True) -> list[StoredRelease]:
    return load_stored_releases(bronze_dir, manifest, REPORT_ID, CropProgressError, strict)


def validate(silver: pd.DataFrame, contract: Contract) -> None:
    contract.enforce(silver)
    if silver.empty:
        return
    # A week may be printed by two releases (2018-09-11 re-issued the 2018-09-10 report with
    # identical national rows): silver keeps both vintages; gold shows the latest and dates
    # availability from the first.
    # Condition ratings of one crop sum to 100 (± rounding) whenever all five are printed.
    cond = silver[(silver.kind == "condition") & silver.value.notna()]
    sums = cond.groupby(["release_key", "crop"])["value"].agg(["sum", "count"])
    bad = sums[(sums["count"] == 5) & ((sums["sum"] - 100).abs() > 1.0)]
    if len(bad):
        raise ContractError(f"condition ratings do not sum to 100: {bad.index.tolist()[:5]}")
