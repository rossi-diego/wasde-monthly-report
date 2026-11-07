"""Pipeline manifest: the audit trail of every ingested report and the published data tag.

The copy inside each GitHub data release is the source of truth; the copy committed to git
(``data/manifest.json``) mirrors it and doubles as monthly repository activity.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReportEntry(BaseModel):
    source: str  # "usda_csv" | "esmis_xml"
    file: str  # path relative to bronze dir
    url: str
    sha256: str
    bytes: int
    release_date: str | None = None
    version: int = 1
    fetched_at: str


class Manifest(BaseModel):
    schema_version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    latest_report: str | None = None
    latest_wasde_number: int | None = None
    data_release_tag: str | None = None
    total_rows: int | None = None
    reports: dict[str, ReportEntry] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.exists():
            return cls()
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.reports = dict(sorted(self.reports.items()))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def summary(self) -> dict[str, Any]:
        return {
            "reports": len(self.reports),
            "first": min(self.reports) if self.reports else None,
            "latest": self.latest_report,
            "tag": self.data_release_tag,
        }
