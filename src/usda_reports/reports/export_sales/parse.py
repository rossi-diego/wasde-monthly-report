"""Export Sales silver: every bronze pull (snapshot) → one long change log in metric tons.

The ESR API overwrites history, so each pull is a snapshot of "what the API said then".
Silver keeps one row per (snapshot, commodity, MY, week, destination, metric) whose value is
new or differs from the previous snapshot that covered the same commodity × MY. A row that
disappears from a later snapshot (the API drops destinations with no activity) is recorded
as a 0-valued tombstone, so "latest value per key" is always the last silver row.

Envelope semantics per row:

* ``release_key`` / ``release_ts_utc``: the ESR release that first published that week —
  the API's ``releaseTimeStamp`` when a pull saw it as the newest week, otherwise the weekly
  calendar (``config/calendars/export_sales.yaml``). ``release_ts_source`` says which:
  ``api``, ``calendar_override`` (a shutdown catch-up week pinned to its actual FAS release
  date) or ``calendar_rule`` (the plain Thursday rule). Catch-up weeks come out *later* than
  the rule, so without the overrides the rule would date them too early and ASOF-join an
  older WASDE than the one public at the real publication.
* ``vintage_quality``: ``latest_only`` for the one-time backfill (values as of the backfill
  day), ``captured`` for every weekly pull from launch on.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from usda_reports.bronze.store import file_sha256
from usda_reports.core.calendar import weekly_release_for
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest, release_ts_utc
from usda_reports.core.vocab import UnseenLabelError, Vocab
from usda_reports.reports.export_sales.source import (
    REPORT_ID,
    SOURCE,
    EsrError,
    SourceConfig,
    decode_bundle,
)
from usda_reports.silver.envelope import ENVELOPE_COLUMNS

log = get_logger(__name__)

KEY = ["commodity_id", "esr_market_year", "week_ending", "country_id", "metric"]
SILVER_COLUMNS = [
    *ENVELOPE_COLUMNS,
    "commodity_id",
    "region_id",
    "unit_id",
    "value",
    "esr_commodity_code",
    "market_year",
    "esr_market_year",
    "my_start",
    "week_ending",
    "week_of_my",
    "country_id",
    "esr_country_code",
    "metric",
    "snapshot_key",
    "snapshot_seq",
    "snapshot_kind",
    "release_ts_source",
]
QUALITY = {"backfill": "latest_only", "weekly": "captured"}

_INT = {"edition", "esr_commodity_code", "esr_market_year", "my_start", "week_of_my"}
_INT |= {"esr_country_code", "snapshot_seq"}
# Explicit Arrow types, so an empty silver (report not ingested yet, or its ingest failed)
# still has the column types the dbt contracts expect.
SILVER_SCHEMA = pa.schema(
    [
        (
            c,
            pa.timestamp("ns", tz="UTC")
            if c == "release_ts_utc"
            else pa.float64()
            if c == "value"
            else pa.date32()
            if c == "week_ending"
            else pa.int32()
            if c in _INT
            else pa.string(),
        )
        for c in SILVER_COLUMNS
    ]
)


def write_silver(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df[SILVER_COLUMNS], schema=SILVER_SCHEMA, preserve_index=False)
    pq.write_table(table, path)
    return path


@dataclass(frozen=True)
class Snapshot:
    key: str
    seq: int
    sha256: str
    edition: int
    bundle: dict[str, Any]


def my_start_months(seed: Path) -> dict[str, int]:
    """commodity_id → marketing-year start month, from ``dbt/seeds/dim_commodity.csv``."""
    with seed.open(encoding="utf-8") as fh:
        return {r["commodity_id"]: int(r["my_start_month"]) for r in csv.DictReader(fh)}


def market_year_label(esr_my: int) -> str:
    """ESR marketYear (end year) → WASDE label: 2027 → '2026/27'."""
    return f"{esr_my - 1}/{esr_my % 100:02d}"


def week_of_my(week_ending: date, my_start: date) -> int:
    """Plan §6: w = floor((week_ending − my_start)/7) + 1."""
    return (week_ending - my_start).days // 7 + 1


def records_frame(
    snap: Snapshot, cfg: SourceConfig, countries: Vocab, starts: dict[str, int]
) -> pd.DataFrame:
    """Long frame (one row per record × metric) of one snapshot; fails on unseen codes/units."""
    by_code = cfg.code_to_commodity()
    rows: list[dict[str, Any]] = []
    unseen: set[int] = set()
    for resp in snap.bundle["responses"]:
        code = int(resp["commodity_code"])
        if code not in by_code:
            raise EsrError(f"snapshot {snap.key}: unexpected commodity code {code}")
        cid = by_code[code]
        esr_my = int(resp["market_year"])
        start = date(esr_my - 1, starts[cid], 1)
        for r in resp["records"]:
            if int(r.get("commodityCode", code)) != code:
                raise EsrError(f"snapshot {snap.key}: record of {r.get('commodityCode')} in {code}")
            if int(r["unitId"]) != cfg.unit.esr_unit_id:
                raise EsrError(f"snapshot {snap.key}: {cid} unitId {r['unitId']} (expected MT)")
            ccode = int(r["countryCode"])
            try:
                country = countries.resolve(f"esr:{ccode}")
            except UnseenLabelError:
                unseen.add(ccode)
                continue
            we = date.fromisoformat(str(r["weekEndingDate"])[:10])
            base = {
                "commodity_id": cid,
                "esr_commodity_code": code,
                "esr_market_year": esr_my,
                "my_start": esr_my - 1,
                "week_ending": we,
                "week_of_my": week_of_my(we, start),
                "country_id": country,
                "esr_country_code": ccode,
            }
            for metric, field in cfg.metrics.items():
                v = r.get(field)
                rows.append({**base, "metric": metric, "value": float(v) if v is not None else 0.0})
    if unseen:
        raise UnseenLabelError(
            f"unseen ESR country codes {sorted(unseen)}: run `usda-reports esr-vocab`"
        )
    df = pd.DataFrame(rows)
    df["snapshot_key"] = snap.key
    df["snapshot_seq"] = snap.seq
    return df


def change_log(frames: list[pd.DataFrame], coverage: list[set[tuple[str, int]]]) -> pd.DataFrame:
    """Keep only new/changed values per key across snapshots; add 0-valued tombstones for
    keys a later snapshot (covering the same commodity × MY) no longer lists."""
    out: list[pd.DataFrame] = []
    latest: pd.DataFrame | None = None  # last known value per key
    for df, cov in zip(frames, coverage, strict=True):
        if latest is not None and len(latest):
            covered = latest[
                [
                    (c, m) in cov
                    for c, m in zip(latest.commodity_id, latest.esr_market_year, strict=True)
                ]
            ]
            newest = df.groupby(["commodity_id", "esr_market_year"])["week_ending"].max()
            covered = covered.join(
                newest.rename("newest_week"), on=["commodity_id", "esr_market_year"]
            )
            covered = covered[covered.week_ending <= covered.newest_week]
            merged = covered.merge(df[[*KEY]], on=KEY, how="left", indicator=True)
            gone = merged[(merged["_merge"] == "left_only") & (merged["value"] != 0)]
            if len(gone):
                tomb = gone.drop(columns=["_merge", "newest_week"]).copy()
                tomb["value"] = 0.0
                tomb["snapshot_key"] = df["snapshot_key"].iloc[0]
                tomb["snapshot_seq"] = df["snapshot_seq"].iloc[0]
                df = pd.concat([df, tomb[df.columns]], ignore_index=True)
            prev = latest[[*KEY, "value"]].rename(columns={"value": "prev"})
            df = df.merge(prev, on=KEY, how="left")
            changed = df[df["prev"].isna() | (df["prev"] != df["value"])].drop(columns="prev")
        else:
            changed = df
        out.append(changed)
        latest = (
            pd.concat([latest, changed], ignore_index=True) if latest is not None else changed
        ).drop_duplicates(KEY, keep="last")
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def release_map(
    snapshots: list[Snapshot], calendar_raw: dict[str, Any], release_time_et: str
) -> dict[date, tuple[str, str, str]]:
    """week_ending → (release_key, release_ts_utc, source) for the newest week of each pull
    (the API's own release stamp). Other weeks are dated with the calendar rule."""
    truth: dict[date, tuple[str, str, str]] = {}
    for s in snapshots:
        weeks = [
            date.fromisoformat(str(r["weekEndingDate"])[:10])
            for resp in s.bundle["responses"]
            for r in resp["records"]
        ]
        if not weeks:
            continue
        newest = max(weeks)
        rel = date.fromisoformat(s.bundle["release_key"])
        # Sanity: a release covers the week that ended 5–14 days earlier.
        if timedelta(days=5) <= rel - newest <= timedelta(days=14):
            at = str(s.bundle.get("release_time_et") or release_time_et)
            ts = release_ts_utc(rel, at)
            assert ts is not None
            truth.setdefault(newest, (rel.isoformat(), ts, "api"))
    return truth


def release_ts_source_for(calendar_raw: dict[str, Any], week_ending: date) -> str:
    """``calendar_override`` when the calendar pins this week to a special (catch-up) date."""
    lag = int((calendar_raw.get("rule") or {}).get("lag_days", 7))
    overrides = {str(k) for k in (calendar_raw.get("overrides") or {})}
    scheduled = (week_ending + timedelta(days=lag)).isoformat()
    return "calendar_override" if scheduled in overrides else "calendar_rule"


def build_frame(
    snapshots: list[Snapshot],
    cfg: SourceConfig,
    countries: Vocab,
    starts: dict[str, int],
    calendar_raw: dict[str, Any],
    release_time_et: str = "08:30",
) -> pd.DataFrame:
    """Silver frame (envelope first) from snapshots in pull order."""
    if not snapshots:
        return pd.DataFrame(columns=SILVER_COLUMNS)
    frames = [records_frame(s, cfg, countries, starts) for s in snapshots]
    coverage = [
        {
            (cfg.code_to_commodity()[int(r["commodity_code"])], int(r["market_year"]))
            for r in s.bundle["responses"]
        }
        for s in snapshots
    ]
    df = change_log(frames, coverage)
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLUMNS)

    truth = release_map(snapshots, calendar_raw, release_time_et)
    weeks = sorted(set(df["week_ending"]))
    rel: dict[date, tuple[str, str, str]] = {}
    for w in weeks:
        if w in truth:
            rel[w] = truth[w]
            continue
        d = weekly_release_for(calendar_raw, w)
        if d is None:  # cancelled release: the week came out with the next one
            d = weekly_release_for(calendar_raw, w + timedelta(days=7))
        assert d is not None
        ts = release_ts_utc(d, release_time_et)
        assert ts is not None
        rel[w] = (d.isoformat(), ts, release_ts_source_for(calendar_raw, w))
    by_seq = {s.seq: s for s in snapshots}

    df["report_id"] = REPORT_ID
    df["release_key"] = df["week_ending"].map(lambda w: rel[w][0])
    df["release_ts_utc"] = pd.to_datetime(df["week_ending"].map(lambda w: rel[w][1]), utc=True)
    df["release_ts_source"] = df["week_ending"].map(lambda w: rel[w][2])
    df["edition"] = df["snapshot_seq"].map(lambda q: by_seq[q].edition).astype("int32")
    df["source"] = SOURCE
    df["bronze_sha256"] = df["snapshot_seq"].map(lambda q: by_seq[q].sha256)
    df["snapshot_kind"] = df["snapshot_seq"].map(lambda q: by_seq[q].bundle["kind"])
    df["vintage_quality"] = df["snapshot_kind"].map(QUALITY)
    df["region_id"] = "united_states"
    df["unit_id"] = cfg.unit.unit_id
    df["market_year"] = df["esr_market_year"].map(market_year_label)
    df["week_ending"] = pd.to_datetime(df["week_ending"]).dt.date
    for c in ("esr_commodity_code", "esr_market_year", "my_start", "week_of_my", "snapshot_seq"):
        df[c] = df[c].astype("int32")
    df["esr_country_code"] = df["esr_country_code"].astype("int32")
    df = df[SILVER_COLUMNS].sort_values(["snapshot_seq", *KEY], kind="stable")
    return df.reset_index(drop=True)


def load_snapshots(bronze_dir: Path, manifest: Manifest) -> list[Snapshot]:
    """Every ok ESR bronze entry in pull order (release key, then edition), sha256-verified."""
    entries = manifest.report(REPORT_ID).ok()
    out = []
    for seq, (key, e) in enumerate(sorted(entries.items(), key=lambda kv: (kv[0], kv[1].edition))):
        assert e.file is not None
        path = bronze_dir / e.file
        if not path.exists() or file_sha256(path) != e.sha256:
            raise EsrError(f"bronze {e.file}: missing or sha256 mismatch")
        out.append(
            Snapshot(
                key=key,
                seq=seq + 1,
                sha256=str(e.sha256),
                edition=e.edition,
                bundle=decode_bundle(path.read_bytes()),
            )
        )
    return out


def validate(silver: pd.DataFrame, contract: Contract, cfg: SourceConfig) -> None:
    contract.enforce(silver)
    if silver.empty:
        return
    newest = silver[silver["release_key"] == silver["release_key"].max()]
    missing = set(cfg.commodities) - set(newest["commodity_id"])
    if missing:
        raise ContractError(f"newest ESR release lacks commodities {sorted(missing)}")
