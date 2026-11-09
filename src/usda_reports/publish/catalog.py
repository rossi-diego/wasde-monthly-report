"""``catalog.json``: where every published file lives (plan §7 'Hosting').

The site is built from one data tag; this file records it and gives, per catalogue file, the
GitHub release URL (release assets are not CORS-readable, so large files are plain links) and,
for files also served by the site, the site path. ``make demo`` and the README resolve
downloads through the live ``catalog.json`` so a reviewer sees the same data as the site.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from usda_reports.core.registry import Registry

SCHEMA_VERSION = 1


def release_download(repo: str, tag: str | None, name: str) -> str | None:
    return f"https://github.com/{repo}/releases/download/{tag}/{name}" if tag else None


def build_catalog(
    entries: list[dict[str, Any]],
    tag: str | None,
    repo: str,
    registry: Registry,
    reports_meta: dict[str, dict[str, Any]],
    site_files: set[str],
) -> dict[str, Any]:
    files = []
    for e in entries:
        files.append(
            {
                "file": e["file"],
                "report_id": e["report_id"],
                "dataset": e["dataset"],
                "schema_version": e["schema_version"],
                "format": e["format"],
                "rows": e["rows"],
                "bytes": e["bytes"],
                "sha256": e["sha256"],
                "coverage": e.get("coverage"),
                "latest_release_key": e.get("latest_release_key"),
                "legacy_alias_of": e.get("legacy_alias_of"),
                "release_url": release_download(repo, tag, e["file"]),
                "site_url": f"data/downloads/{e['file']}" if e["file"] in site_files else None,
            }
        )
    reports = {}
    for rid, cfg in registry.reports.items():
        if not cfg.enabled:
            continue
        reports[rid] = {
            "title": cfg.title,
            "agency": cfg.agency,
            "cadence": cfg.cadence,
            "licence": cfg.licence,
            **reports_meta.get(rid, {}),
        }
    if "export_sales" in reports:
        reports["export_sales"]["vintage_note"] = "latest_only_before_first_capture_then_captured"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo": repo,
        "data_tag": tag,
        "release_page": f"https://github.com/{repo}/releases/tag/{tag}" if tag else None,
        "datapackage": {
            "file": "datapackage.json",
            "site_url": "data/datapackage.json",
            "release_url": release_download(repo, tag, "datapackage.json"),
        },
        "web_data": {
            "file": "web-data.tar.gz",
            "release_url": release_download(repo, tag, "web-data.tar.gz"),
        },
        "reports": reports,
        "files": files,
    }
