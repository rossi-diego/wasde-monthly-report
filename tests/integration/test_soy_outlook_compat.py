"""Soy Outlook compatibility: what it downloads must keep passing its own acceptance checks.

Soy Outlook (sarimax-brazilian-soybean-forecasting) reads ``meta.json`` (``data_release_tag``,
``next_release``) and ``wasde_full.parquet`` from this repository's releases, then runs
``wasde_problems`` (mirrored in ``usda_reports.publish.contract.soy_outlook_problems``).
"""

from __future__ import annotations

import json

import pandas as pd

from usda_reports.core.config import Settings
from usda_reports.publish.contract import (
    SOY_OUTLOOK_REQUIRED_COLUMNS,
    soy_outlook_problems,
)


def test_alias_passes_soy_outlook_checks(built: Settings):
    df = pd.read_parquet(built.publish_dir / "wasde_full.parquet")
    assert soy_outlook_problems(df) == []
    assert set(df.columns) >= SOY_OUTLOOK_REQUIRED_COLUMNS
    # The alias keeps its legacy schema: no envelope columns leak into it.
    assert "report_id" not in df.columns and "bronze_sha256" not in df.columns


def test_alias_is_byte_identical_everywhere(built: Settings):
    v1 = (built.publish_dir / "wasde__values__v1.parquet").read_bytes()
    assert (built.publish_dir / "wasde_full.parquet").read_bytes() == v1
    assert (built.web_data_dir / "downloads" / "wasde_full.parquet").read_bytes() == v1


def test_meta_keys_soy_outlook_reads(built: Settings):
    meta = json.loads((built.publish_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["data_release_tag"] == "data-2024-05"
    assert "next_release" in meta
    assert any(d["file"] == "wasde_full.parquet" for d in meta["downloads"])


def test_checks_reject_what_would_break_soy_outlook(built: Settings):
    df = pd.read_parquet(built.publish_dir / "wasde_full.parquet")
    assert soy_outlook_problems(df.drop(columns=["unit_id"]))
    assert soy_outlook_problems(pd.concat([df, df.head(1)]))  # duplicated key
    assert soy_outlook_problems(df.assign(report_month="Oct 2026"))
