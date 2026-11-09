"""Release and tag contract (plan §7): ``releases/latest`` must stay a ``data-*`` tag with the
meta keys and the ``wasde_full.parquet`` alias that downstream users depend on.

The offline tests check what a build publishes; the live test (``USDA_LIVE_TESTS=1``) checks
the real GitHub ``releases/latest`` of this repository.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from usda_reports.core.config import Settings
from usda_reports.publish.contract import release_contract_problems

REPO = "rossi-diego/usda-reports-dashboard"


def test_built_release_meets_contract(built: Settings):
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assets = [p.name for p in built.publish_dir.iterdir()] + ["manifest.json"]
    assert release_contract_problems("data-2024-05", meta, assets) == []


def test_contract_catches_breaking_changes(built: Settings):
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assets = ["meta.json", "manifest.json", "wasde_full.parquet"]
    assert release_contract_problems("weekly-2026-11-12", meta, assets)  # not a data-* tag
    no_alias = release_contract_problems("data-2024-05", meta, assets[:2])
    assert any("wasde_full.parquet" in p for p in no_alias)
    stripped = {k: v for k, v in meta.items() if k != "next_release"}
    assert any(
        "next_release" in p for p in release_contract_problems("data-2024-05", stripped, assets)
    )


def test_current_v1_release_meta_still_valid(fixtures):
    """The live data-2026-10 meta (pre-`reports` map) satisfies the legacy part of the contract."""
    meta = json.loads((fixtures / "release" / "meta_data-2026-10.json").read_text(encoding="utf-8"))
    assets = ["meta.json", "manifest.json", "wasde_full.parquet", "bronze.tar.gz"]
    assert release_contract_problems("data-2026-10", meta, assets, require_reports=False) == []


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("USDA_LIVE_TESTS") != "1", reason="set USDA_LIVE_TESTS=1")
def test_live_latest_release_contract():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    with httpx.Client(follow_redirects=True, timeout=60, headers=headers) as client:
        rel = client.get(f"https://api.github.com/repos/{REPO}/releases/latest").json()
        tag = rel["tag_name"]
        assets = [a["name"] for a in rel["assets"]]
        meta = client.get(f"https://github.com/{REPO}/releases/download/{tag}/meta.json").json()
    assert release_contract_problems(tag, meta, assets, require_reports=False) == []
