"""catalog-diff: breaking catalogue changes need a new major schema_version."""

from __future__ import annotations

import json

from usda_reports.core.config import PROJECT_ROOT
from usda_reports.publish.catalogue import ALL_DATASETS
from usda_reports.publish.schema_diff import compare, load_snapshot, snapshot_from_datapackage

SNAPSHOT = PROJECT_ROOT / "docs" / "schemas" / "catalog.schema.json"


def snap(datasets: dict) -> dict:
    return {"snapshot_version": 1, "datasets": datasets}


def ds(fields: dict, major: int = 1, report: str = "grain_stocks", name: str = "quarterly") -> dict:
    return {
        "report_id": report,
        "dataset": name,
        "schema_version": major,
        "model": "m",
        "fields": fields,
    }


def test_removed_renamed_retyped_columns_are_breaking():
    old = snap({"grain_stocks__quarterly__v1": ds({"a": "string", "b": "number", "c": "date"})})
    new = snap({"grain_stocks__quarterly__v1": ds({"a": "string", "b": "integer", "d": "date"})})
    d = compare(old, new)
    assert not d.ok
    assert any("'b' retyped number -> integer" in x for x in d.breaking)
    assert any("'c' removed or renamed" in x for x in d.breaking)
    assert d.additive == ["grain_stocks__quarterly__v1: new column 'd'"]


def test_added_columns_and_datasets_are_not_breaking():
    old = snap({"grain_stocks__quarterly__v1": ds({"a": "string"})})
    new = snap(
        {
            "grain_stocks__quarterly__v1": ds({"a": "string", "z": "number"}),
            "crop_progress__weekly__v1": ds({"x": "date"}, report="crop_progress", name="weekly"),
        }
    )
    d = compare(old, new)
    assert d.ok and len(d.additive) == 2


def test_dataset_removal_needs_a_major_bump():
    old = snap({"grain_stocks__quarterly__v1": ds({"a": "string"})})
    assert not compare(old, snap({})).ok
    bumped = snap({"grain_stocks__quarterly__v2": ds({"b": "number"}, major=2)})
    assert compare(old, bumped).ok


def test_datapackage_baseline_and_committed_snapshot_cover_the_catalogue():
    pkg = {
        "resources": [
            {"path": "x__y__v1.parquet", "format": "parquet", "report_id": "x", "dataset": "y",
             "schema_version": 1, "dbt_model": "m",
             "schema": {"fields": [{"name": "a", "type": "string"}]}},
            {"path": "x__y__v1.csv", "format": "csv", "schema": {"fields": []}},
        ]
    }  # fmt: skip
    assert snapshot_from_datapackage(pkg)["datasets"]["x__y__v1"]["fields"] == {"a": "string"}
    committed = load_snapshot(SNAPSHOT)
    assert set(committed["datasets"]) == {d.stem for d in ALL_DATASETS}
    assert json.loads(SNAPSHOT.read_text(encoding="utf-8"))["snapshot_version"] == 1
