"""Pipeline manifest: the audit trail of every ingested release and the published data tag.

The copy inside each GitHub data release is the source of truth; the copy committed to git
(``data/manifest.json``) mirrors it and doubles as repository activity.

Schema v2 is multi-report::

    {
      "schema_version": 2,
      "data_release_tag": "data-2026-10",
      "reports": {
        "wasde": {
          "latest_release_key": "2026-10",
          "latest_number": 676,
          "total_rows": 852915,
          "releases": {
            "2026-10": {"source": "usda_csv", "file": "usda_csv/2026-10.csv", "sha256": "…",
                        "release_ts_utc": "2026-10-09T16:00:00+00:00", "edition": 1,
                        "status": "ok", "shard": "bronze__wasde__base.tar.gz", …}
          }
        }
      }
    }

``Manifest.load`` upgrades a v1 file (WASDE only, keyed by month) in memory with
:func:`migrate_v1`; the next ``save`` writes v2.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

SCHEMA_VERSION = 2
EASTERN = ZoneInfo("America/New_York")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def release_ts_utc(release_date: str | date | None, release_time_et: str = "12:00") -> str | None:
    """ISO UTC timestamp of a release published on ``release_date`` at ``release_time_et`` ET."""
    if release_date is None:
        return None
    try:
        d = (
            release_date
            if isinstance(release_date, date)
            else date.fromisoformat(str(release_date)[:10])
        )
    except ValueError:
        return None
    hh, mm = (int(x) for x in release_time_et.split(":"))
    ts = datetime.combine(d, time(hh, mm), EASTERN).astimezone(UTC)
    return ts.isoformat(timespec="seconds")


class ReleaseEntry(BaseModel):
    """One release (edition) of one report as stored in bronze."""

    source: str  # e.g. "usda_csv" | "esmis_xml"
    file: str | None = None  # path relative to the bronze dir; None when skipped
    url: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    release_date: str | None = None  # ISO date as published by the source
    release_ts_utc: str | None = None  # release instant (calendar time in ET, stored as UTC)
    edition: int = 1  # revised editions ("v2") of the same release key
    fetched_at: str = Field(default_factory=_now)
    status: Literal["ok", "skipped"] = "ok"
    shard: str | None = None  # bronze-store shard holding ``file`` (None = not uploaded yet)


class ReportState(BaseModel):
    latest_release_key: str | None = None
    latest_number: int | None = None  # report-specific running number (e.g. WASDE-676)
    total_rows: int | None = None
    # Every bronze-store shard ever written for this report (append-only; names are never
    # reused even when a re-ingested edition no longer points at an old shard).
    shards_written: list[str] = Field(default_factory=list)
    releases: dict[str, ReleaseEntry] = Field(default_factory=dict)

    def ok(self) -> dict[str, ReleaseEntry]:
        return {k: e for k, e in sorted(self.releases.items()) if e.status == "ok"}


class Manifest(BaseModel):
    schema_version: int = SCHEMA_VERSION
    updated_at: str = Field(default_factory=_now)
    data_release_tag: str | None = None
    reports: dict[str, ReportState] = Field(default_factory=dict)

    # ── access ───────────────────────────────────────────────────────────────

    def report(self, report_id: str) -> ReportState:
        """State for ``report_id`` (created empty on first use)."""
        return self.reports.setdefault(report_id, ReportState())

    def releases(self, report_id: str) -> dict[str, ReleaseEntry]:
        return self.report(report_id).releases

    def shards(self, report_id: str | None = None) -> set[str]:
        """Shards referenced by current releases (what a restore needs)."""
        ids = [report_id] if report_id else list(self.reports)
        return {
            e.shard
            for rid in ids
            for e in self.report(rid).releases.values()
            if e.shard is not None
        }

    # ── io ───────────────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Manifest:
        if int(raw.get("schema_version", 1)) < SCHEMA_VERSION:
            raw = migrate_v1(raw)
        return cls.model_validate(raw)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        self.updated_at = _now()
        self.schema_version = SCHEMA_VERSION
        self.reports = dict(sorted(self.reports.items()))
        for state in self.reports.values():
            state.releases = dict(sorted(state.releases.items()))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"tag": self.data_release_tag}
        for rid, state in self.reports.items():
            keys = list(state.ok())
            out[rid] = {
                "releases": len(keys),
                "first": keys[0] if keys else None,
                "latest": keys[-1] if keys else None,
            }
        return out


def migrate_v1(raw: dict[str, Any], release_time_et: str = "12:00") -> dict[str, Any]:
    """Upgrade a v1 manifest (WASDE only, ``reports`` keyed by month) to the v2 layout.

    Nothing is lost: ``version`` becomes ``edition``, the release instant is derived from the
    release date and WASDE's 12:00 ET publication time, and every file is marked as not yet
    stored in a bronze-store shard.
    """
    releases = {}
    for key, e in (raw.get("reports") or {}).items():
        releases[key] = {
            "source": e["source"],
            "file": e.get("file"),
            "url": e.get("url"),
            "sha256": e.get("sha256"),
            "bytes": e.get("bytes"),
            "release_date": e.get("release_date"),
            "release_ts_utc": release_ts_utc(e.get("release_date"), release_time_et),
            "edition": int(e.get("version", 1)),
            "fetched_at": e.get("fetched_at") or _now(),
            "status": "ok",
            "shard": None,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": raw.get("updated_at") or _now(),
        "data_release_tag": raw.get("data_release_tag"),
        "reports": {
            "wasde": {
                "latest_release_key": raw.get("latest_report"),
                "latest_number": raw.get("latest_wasde_number"),
                "total_rows": raw.get("total_rows"),
                "releases": releases,
            }
        },
    }
