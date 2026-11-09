"""Release and tag contract that protects downstream users (plan §7).

Soy Outlook resolves ``releases/latest/download/meta.json``, reads ``data_release_tag`` and
``next_release`` from it and downloads ``wasde_full.parquet`` from that tag. So the latest
release must be a ``data-*`` tag carrying ``meta.json`` with those keys and the alias, and the
parquet must pass Soy Outlook's own acceptance checks (mirrored here).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

DATA_TAG_RE = re.compile(r"^data-\d{4}-\d{2}$")
# Weekly builds (Export Sales) are immutable prereleases, never "Latest".
WEEKLY_TAG_RE = re.compile(r"^weekly-\d{4}-\d{2}-\d{2}(\.\d+)?$")


def weekly_tag(day: date, existing: set[str]) -> str:
    """``weekly-YYYY-MM-DD``; ``.2``, ``.3``… when a release with that tag already exists
    (weekly releases are immutable, so a second change the same day gets a new tag)."""
    base = f"weekly-{day.isoformat()}"
    if base not in existing:
        return base
    n = 2
    while f"{base}.{n}" in existing:
        n += 1
    return f"{base}.{n}"


def datasets_changed(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[str]:
    """Files whose sha256 differs between two ``datasets.json`` (added and removed files
    included). Empty = the catalogue may keep pointing at the old, immutable release."""
    a = {str(e["file"]): e.get("sha256") for e in old}
    b = {str(e["file"]): e.get("sha256") for e in new}
    return sorted(f for f in a.keys() | b.keys() if a.get(f) != b.get(f))


def is_release_tag(tag: str) -> bool:
    return bool(DATA_TAG_RE.match(tag) or WEEKLY_TAG_RE.match(tag))


REQUIRED_ASSETS = ("meta.json", "manifest.json", "wasde_full.parquet")
REQUIRED_META_KEYS = ("data_release_tag", "next_release", "latest", "history", "downloads")
REQUIRED_LATEST_KEYS = ("report_month", "label", "wasde_number", "release_date")
REQUIRED_REPORT_KEYS = ("latest_release_key", "release_ts_utc", "next_release", "rows")

# Mirrors soyforecast.ingest.wasde (REQUIRED_COLUMNS / KEY_COLUMNS / wasde_problems).
SOY_OUTLOOK_REQUIRED_COLUMNS = frozenset(
    {
        "report_month",
        "release_date",
        "table_id",
        "commodity_id",
        "region_id",
        "attribute_id",
        "market_year",
        "period",
        "value",
        "unit_id",
    }
)
SOY_OUTLOOK_KEY_COLUMNS = (
    "report_month",
    "table_id",
    "commodity_id",
    "region_id",
    "attribute_id",
    "market_year",
    "period",
    "reliability_stat",
)
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def release_contract_problems(
    tag: str, meta: dict[str, Any], assets: list[str], require_reports: bool = True
) -> list[str]:
    """Reasons a release would break downstream users (empty list = contract holds)."""
    problems = []
    if not DATA_TAG_RE.match(tag):
        problems.append(f"latest release {tag!r} is not a data-YYYY-MM tag")
    missing_assets = [a for a in REQUIRED_ASSETS if a not in assets]
    if missing_assets:
        problems.append(f"missing assets {missing_assets}")
    missing = [k for k in REQUIRED_META_KEYS if k not in meta]
    if missing:
        problems.append(f"meta.json missing keys {missing}")
    if meta.get("data_release_tag") != tag:
        problems.append(f"meta.data_release_tag {meta.get('data_release_tag')!r} != tag {tag!r}")
    latest = meta.get("latest") or {}
    missing_latest = [k for k in REQUIRED_LATEST_KEYS if k not in latest]
    if missing_latest:
        problems.append(f"meta.latest missing keys {missing_latest}")
    if require_reports or "reports" in meta:
        wasde = (meta.get("reports") or {}).get("wasde")
        if wasde is None:
            problems.append("meta.reports.wasde missing")
        else:
            missing_r = [k for k in REQUIRED_REPORT_KEYS if k not in wasde]
            if missing_r:
                problems.append(f"meta.reports.wasde missing keys {missing_r}")
            if latest.get("report_month") and wasde.get("latest_release_key") != latest.get(
                "report_month"
            ):
                problems.append("meta.reports.wasde.latest_release_key != meta.latest.report_month")
    return problems


def soy_outlook_problems(df: pd.DataFrame) -> list[str]:
    """Soy Outlook's acceptance checks for ``wasde_full.parquet`` (without its cache rules)."""
    missing = SOY_OUTLOOK_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return [f"missing columns: {sorted(missing)}"]
    if df.empty:
        return ["no rows"]
    problems: list[str] = []
    if not pd.api.types.is_numeric_dtype(df["value"]):
        problems.append(f"value column is {df['value'].dtype}, not numeric")
    months = df["report_month"].astype(str)
    if not months.map(lambda m: bool(_MONTH_RE.match(m))).all():
        problems.append("report_month is not YYYY-MM everywhere")
    if pd.to_datetime(df["release_date"], errors="coerce").isna().any():
        problems.append("release_date has missing or unparseable values")
    keys = [k for k in SOY_OUTLOOK_KEY_COLUMNS if k in df.columns]
    dups = int(df.duplicated(keys).sum())
    if dups:
        problems.append(f"{dups} duplicated keys")
    return problems
