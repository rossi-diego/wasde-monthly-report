"""PARITY GATE: a full rebuild from real bronze reproduces the published WASDE dataset.

Needs the real bronze store (``data/bronze`` + ``data/manifest.json``, ~300 MB) and the
published reference ``wasde_full.parquet`` (default ``data/parity/wasde_full.parquet``, e.g.
``gh release download data-2026-10 --pattern wasde_full.parquet --dir data/parity``; or set
``USDA_PARITY_REFERENCE``). Skipped when either is absent, so CI stays fast and offline.

It proves that ``wasde__values__v1`` and its legacy alias ``wasde_full.parquet`` have the same
row count, schema and sorted-content hash as the reference, and that the alias is
byte-identical to ``wasde__values__v1.parquet``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest

from usda_reports.core.config import PROJECT_ROOT, Settings
from usda_reports.core.manifest import Manifest
from usda_reports.core.parity import fingerprint
from usda_reports.publish.contract import soy_outlook_problems

BRONZE = PROJECT_ROOT / "data" / "bronze"
MANIFEST = PROJECT_ROOT / "data" / "manifest.json"
REFERENCE = Path(
    os.environ.get("USDA_PARITY_REFERENCE", PROJECT_ROOT / "data" / "parity" / "wasde_full.parquet")
)


def _bronze_complete() -> bool:
    if not (MANIFEST.exists() and REFERENCE.exists()):
        return False
    entries = Manifest.load(MANIFEST).report("wasde").ok()
    return bool(entries) and all(e.file and (BRONZE / e.file).exists() for e in entries.values())


pytestmark = [
    pytest.mark.skipif(not _bronze_complete(), reason="real bronze or reference parquet absent"),
    pytest.mark.slow,
]


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory) -> tuple[Settings, dict[str, float]]:
    pytest.importorskip("dbt")
    from usda_reports.gold import run_dbt
    from usda_reports.publish.run import publish_all
    from usda_reports.silver.build import build_all

    root = tmp_path_factory.mktemp("parity")
    settings = Settings(
        data_dir=root / "data",
        web_data_dir=root / "web",
        config_dir=PROJECT_ROOT / "config",
        bronze_path=BRONZE,
    )
    manifest = Manifest.load(MANIFEST)
    timing: dict[str, float] = {}
    t0 = time.perf_counter()
    result = build_all(settings, manifest)
    timing["silver_s"] = time.perf_counter() - t0
    assert not result.alerts
    t0 = time.perf_counter()
    assert run_dbt(settings) == 0  # full `dbt build`: seeds, models and every data test
    timing["gold_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    publish_all(settings, manifest, tag=manifest.data_release_tag)
    timing["publish_s"] = time.perf_counter() - t0
    print(f"\nparity rebuild timing: {json.dumps({k: round(v, 1) for k, v in timing.items()})}")
    return settings, timing


def test_parity_wasde(rebuilt):
    settings, _ = rebuilt
    ref = fingerprint(REFERENCE)
    values = settings.publish_dir / "wasde__values__v1.parquet"
    alias = settings.publish_dir / "wasde_full.parquet"
    for path in (values, alias, settings.web_data_dir / "downloads" / "wasde_full.parquet"):
        fp = fingerprint(path)
        assert fp.rows == ref.rows, path.name
        assert fp.schema == ref.schema, path.name
        assert fp.content_sha256 == ref.content_sha256, path.name
    assert alias.read_bytes() == values.read_bytes()


def test_soy_outlook_accepts_rebuilt_alias(rebuilt):
    settings, _ = rebuilt
    df = pd.read_parquet(settings.publish_dir / "wasde_full.parquet")
    assert soy_outlook_problems(df) == []
    meta = json.loads((settings.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["history"]["rows"] == len(df) == meta["reports"]["wasde"]["rows"]


def test_silver_carries_the_envelope(rebuilt):
    settings, timing = rebuilt
    silver = pd.read_parquet(settings.silver_dir / "wasde.parquet")
    assert silver["report_id"].eq("wasde").all()
    assert silver["vintage_quality"].eq("as_published").all()
    assert silver[["release_key", "release_ts_utc", "bronze_sha256"]].notna().all().all()
    assert (silver["release_key"] == silver["report_month"]).all()
    assert timing["silver_s"] < 300, "silver reparse over 5 min: enable the actions/cache"
