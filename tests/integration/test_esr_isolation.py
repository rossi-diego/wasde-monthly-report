"""Per-report isolation: a bad Export Sales snapshot must never block WASDE gold or publish.

Bronze holds the good fixture pull (2025-09-11) and a later pull (2025-09-18) with a FAS
destination code the vocabulary has never seen. The silver build falls back to the last good
ESR state, records the failure, and dbt + publish (meta.json, wasde_full.parquet: the Soy
Outlook contract) still succeed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from tests.integration.conftest import BUILT_NOW, mini_settings, write_wasde_silver
from usda_reports.bronze.store import BronzeStore
from usda_reports.core.manifest import Manifest
from usda_reports.publish.contract import release_contract_problems
from usda_reports.reports.export_sales.source import encode_bundle
from usda_reports.silver.build import build_all, failed_reports, write_status

UNSEEN = 99999


def _bundles(fixtures: Path) -> tuple[dict, dict]:
    good = json.loads((fixtures / "export_sales" / "bundle_2025-09-11.json").read_text("utf-8"))
    bad = copy.deepcopy(good)
    bad["kind"] = "weekly"
    bad["release_key"] = "2025-09-18"
    rec = copy.deepcopy(bad["responses"][0]["records"][0])
    rec["countryCode"] = UNSEEN
    bad["responses"][0]["records"].append(rec)
    return good, bad


def _put(store: BronzeStore, bundle: dict) -> None:
    store.put(
        bundle["release_key"],
        encode_bundle(bundle),
        source="fas_esr_api",
        url="https://api.fas.usda.gov",
        release_date=bundle["release_key"],
    )


def test_unseen_country_code_does_not_block_wasde(tmp_path, fixtures):
    pytest.importorskip("dbt")
    from usda_reports.gold import run_dbt
    from usda_reports.publish.run import publish_all

    settings = mini_settings(tmp_path)
    manifest = write_wasde_silver(settings, fixtures)
    good, bad = _bundles(fixtures)
    store = BronzeStore(settings.bronze_dir, manifest, "export_sales", "08:30")
    _put(store, good)
    _put(store, bad)

    result = build_all(settings, manifest, only="export_sales")
    assert set(result.failed) == {"export_sales"} and str(UNSEEN) in result.failed["export_sales"]
    write_status(settings, result)
    assert failed_reports(settings) == {"export_sales"}
    esr = pd.read_parquet(settings.silver_dir / "export_sales.parquet")
    assert len(esr) and set(esr.snapshot_key) == {"2025-09-11"}  # the last good state

    assert run_dbt(settings, command="run") == 0
    publish_all(settings, manifest, tag="data-2024-05", now=BUILT_NOW)
    meta = json.loads((settings.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["data_release_tag"] == "data-2024-05" and meta["latest"]
    assert meta["reports"]["export_sales"]["latest_release_key"] == "2025-09-11"
    assert (settings.publish_dir / "wasde_full.parquet").stat().st_size > 0
    assets = [p.name for p in settings.publish_dir.iterdir()] + ["manifest.json"]
    assert release_contract_problems("data-2024-05", meta, assets) == []


def test_only_bad_snapshots_leave_an_empty_esr_silver(tmp_path, fixtures):
    settings = mini_settings(tmp_path)
    settings.silver_dir.mkdir(parents=True)
    manifest = Manifest()
    _, bad = _bundles(fixtures)
    _put(BronzeStore(settings.bronze_dir, manifest, "export_sales", "08:30"), bad)
    result = build_all(settings, manifest, only="export_sales")
    assert set(result.failed) == {"export_sales"} and result.rows["export_sales"] == 0
    empty = pd.read_parquet(settings.silver_dir / "export_sales.parquet")
    assert empty.empty and "release_ts_utc" in empty.columns
