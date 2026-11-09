"""Release retention (plan §7): which superseded ``weekly-*`` prereleases may be pruned.

Rules, in order (a release is pruned only when every rule allows it):

1. Only tags matching ``weekly-YYYY-MM-DD[.N]`` that are **prereleases**, not drafts and not
   marked Latest are candidates. ``data-*`` releases (kept forever, Soy Outlook reads the
   Latest one), ``bronze-store`` (append-only shards every data-* manifest points at) and any
   other tag are never touched.
2. Protected tags are never pruned: the tag the live site was built from (``build.json``
   ``tag`` / ``catalog.json`` ``data_tag``), whose asset URLs the catalogue links to.
3. The newest ``keep_min`` (8) weekly releases are always kept.
4. Of the rest, only those created more than ``keep_days`` (90) days ago are pruned.

The workflow (``.github/workflows/retention.yml``) prints this plan on every run and deletes
only when explicitly asked (manual run with ``apply: true``, or the repository variable
``RETENTION_APPLY`` set to ``true``): it is a dry run by default.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from usda_reports.publish.contract import DATA_TAG_RE, WEEKLY_TAG_RE

KEEP_DAYS = 90
KEEP_MIN = 8
NEVER = frozenset({"bronze-store"})


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    created_at: datetime
    is_prerelease: bool
    is_latest: bool = False
    is_draft: bool = False


def parse_gh_list(rows: Iterable[dict[str, Any]]) -> list[ReleaseInfo]:
    """``gh release list --json tagName,createdAt,isPrerelease,isLatest,isDraft`` rows."""
    out = []
    for r in rows:
        out.append(
            ReleaseInfo(
                tag=str(r["tagName"]),
                created_at=datetime.fromisoformat(str(r["createdAt"]).replace("Z", "+00:00")),
                is_prerelease=bool(r.get("isPrerelease")),
                is_latest=bool(r.get("isLatest")),
                is_draft=bool(r.get("isDraft")),
            )
        )
    return out


def is_candidate(r: ReleaseInfo) -> bool:
    return (
        bool(WEEKLY_TAG_RE.match(r.tag))
        and not DATA_TAG_RE.match(r.tag)
        and r.tag not in NEVER
        and r.is_prerelease
        and not r.is_latest
        and not r.is_draft
    )


def select_prunable(
    releases: Iterable[ReleaseInfo],
    now: datetime,
    keep_days: int = KEEP_DAYS,
    keep_min: int = KEEP_MIN,
    protected: Iterable[str] = (),
) -> list[str]:
    """Tags to delete, oldest first (empty = nothing to prune)."""
    if keep_min < 1 or keep_days < 1:
        raise ValueError("keep_min and keep_days must be at least 1")
    keep = set(protected)
    weekly = sorted(
        (r for r in releases if WEEKLY_TAG_RE.match(r.tag)),
        key=lambda r: (r.created_at, r.tag),
        reverse=True,
    )
    # The newest keep_min weekly releases (candidates or not) are kept.
    newest = {r.tag for r in weekly[:keep_min]}
    cutoff = now - timedelta(days=keep_days)
    out = [
        r.tag
        for r in weekly
        if is_candidate(r) and r.tag not in newest and r.tag not in keep and r.created_at < cutoff
    ]
    return sorted(out, key=lambda t: next(r.created_at for r in weekly if r.tag == t))
