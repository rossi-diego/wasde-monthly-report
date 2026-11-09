"""Release retention selection (.github/workflows/retention.yml): only superseded weekly-*
prereleases beyond the window are pruned; data-*, the Latest release, bronze-store, drafts,
protected tags and the newest 8 weekly releases never are."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from usda_reports.publish.retention import ReleaseInfo, parse_gh_list, select_prunable

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def weekly(days_ago: int, suffix: str = "", **kw) -> ReleaseInfo:
    d = (NOW - timedelta(days=days_ago)).date()
    return ReleaseInfo(
        tag=f"weekly-{d.isoformat()}{suffix}",
        created_at=NOW - timedelta(days=days_ago),
        is_prerelease=kw.pop("is_prerelease", True),
        **kw,
    )


def test_keeps_window_and_newest_eight():
    rels = [weekly(d) for d in range(0, 200, 7)]  # 29 weekly releases, one a week
    pruned = select_prunable(rels, NOW)
    assert pruned  # some are older than 90 days and beyond the newest 8
    ages = {r.tag: (NOW - r.created_at).days for r in rels}
    assert all(ages[t] > 90 for t in pruned)
    newest8 = {r.tag for r in sorted(rels, key=lambda r: r.created_at)[-8:]}
    assert not newest8 & set(pruned)
    assert pruned == sorted(pruned, key=lambda t: ages[t], reverse=True)  # oldest first


def test_newest_eight_kept_even_when_all_are_old():
    rels = [weekly(d) for d in range(300, 300 + 7 * 10, 7)]  # 10 releases, all > 90 days
    pruned = select_prunable(rels, NOW)
    assert len(pruned) == 2


def test_never_touches_data_latest_bronze_drafts_or_protected():
    old = NOW - timedelta(days=400)
    rels = [
        ReleaseInfo("data-2025-01", old, is_prerelease=False),
        ReleaseInfo("data-2026-10", old, is_prerelease=False, is_latest=True),
        ReleaseInfo("bronze-store", old, is_prerelease=True),
        ReleaseInfo("v2.0.0", old, is_prerelease=False),
        weekly(380, is_latest=True),
        weekly(370, is_draft=True),
        weekly(360, is_prerelease=False),  # a weekly tag that is not a prerelease: left alone
        weekly(350),  # protected (the live site points at it)
        weekly(340),  # the only prunable one
        *[weekly(d) for d in range(0, 56, 7)],  # newest 8
    ]
    protected = [rels[7].tag]
    assert select_prunable(rels, NOW, protected=protected) == [rels[8].tag]


def test_same_day_suffix_tags_and_gh_json():
    rows = [
        {"tagName": "weekly-2026-01-05", "createdAt": "2026-01-05T13:00:00Z", "isPrerelease": True,
         "isLatest": False, "isDraft": False},
        {"tagName": "weekly-2026-01-05.2", "createdAt": "2026-01-05T15:00:00Z",
         "isPrerelease": True, "isLatest": False, "isDraft": False},
        {"tagName": "data-2026-01", "createdAt": "2026-01-12T17:00:00Z", "isPrerelease": False,
         "isLatest": True, "isDraft": False},
    ]  # fmt: skip
    rels = parse_gh_list(rows)
    assert select_prunable(rels, NOW, keep_min=1) == ["weekly-2026-01-05"]
    assert select_prunable(rels, NOW, keep_min=2) == []
    with pytest.raises(ValueError):
        select_prunable(rels, NOW, keep_min=0)
