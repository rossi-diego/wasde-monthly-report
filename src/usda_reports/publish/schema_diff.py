"""Catalogue schema guard (plan §7 "Schema guard", CI job ``catalog-diff``).

A *snapshot* is the public shape of the download catalogue: per dataset stem
(``<report_id>__<dataset>__v<major>``) its model and the Table Schema type of every column.

* :func:`snapshot_from_duckdb` builds it from the gold models (works on a fixture build: an
  empty model still has its column types), in the column order of ``config/datasets.yaml``.
* :func:`snapshot_from_datapackage` builds it from a published ``datapackage.json`` (e.g. the
  live site's), so a PR can also be compared with what consumers download today.
* :func:`compare` lists **breaking** changes (a column removed, renamed or retyped, or a dataset
  removed, without a new major version of that dataset) and additive ones (new columns, new
  datasets). Breaking changes need ``schema_version`` + 1 in ``config/datasets.yaml``, which
  publishes a new ``__v<major+1>`` file next to the old one.

The committed snapshot is ``docs/schemas/catalog.schema.json``; a test fails when it drifts
from the models (regenerate with ``usda-reports catalog-schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from usda_reports.publish.catalogue import ALL_DATASETS, Dataset
from usda_reports.publish.datapackage import field_type

SNAPSHOT_VERSION = 1


def snapshot_from_duckdb(
    con: duckdb.DuckDBPyConnection, datasets: list[Dataset] | None = None
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ds in datasets if datasets is not None else ALL_DATASETS:
        cols = con.execute(f"describe {ds.query}").fetchall()
        out[ds.stem] = {
            "report_id": ds.report_id,
            "dataset": ds.dataset,
            "schema_version": ds.major,
            "model": ds.model,
            "fields": {name: field_type(str(typ)) for name, typ, *_ in cols},
        }
    return {"snapshot_version": SNAPSHOT_VERSION, "datasets": dict(sorted(out.items()))}


def snapshot_from_datapackage(pkg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for res in pkg.get("resources") or []:
        if res.get("format") != "parquet":
            continue
        stem = str(res["path"]).split(".", 1)[0]
        out[stem] = {
            "report_id": res.get("report_id"),
            "dataset": res.get("dataset"),
            "schema_version": res.get("schema_version"),
            "model": res.get("dbt_model"),
            "fields": {f["name"]: f.get("type", "any") for f in res["schema"]["fields"]},
        }
    return {"snapshot_version": SNAPSHOT_VERSION, "datasets": dict(sorted(out.items()))}


def load_snapshot(path: Path) -> dict[str, Any]:
    """A snapshot file, or a ``datapackage.json`` converted to one."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return snapshot_from_datapackage(raw) if "resources" in raw else raw


@dataclass
class SchemaDiff:
    breaking: list[str] = field(default_factory=list)
    additive: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.breaking


def compare(old: dict[str, Any], new: dict[str, Any]) -> SchemaDiff:
    """Breaking and additive differences from ``old`` (the baseline) to ``new``."""
    diff = SchemaDiff()
    a, b = old.get("datasets") or {}, new.get("datasets") or {}
    for stem, o in sorted(a.items()):
        n = b.get(stem)
        if n is None:
            bumped = any(
                d.get("report_id") == o.get("report_id")
                and d.get("dataset") == o.get("dataset")
                and int(d.get("schema_version") or 0) > int(o.get("schema_version") or 0)
                for d in b.values()
            )
            if bumped:
                diff.additive.append(f"{stem}: superseded by a new major version")
            else:
                diff.breaking.append(f"{stem}: dataset removed without a new major version")
            continue
        for col, typ in o["fields"].items():
            if col not in n["fields"]:
                diff.breaking.append(f"{stem}: column {col!r} removed or renamed")
            elif n["fields"][col] != typ:
                diff.breaking.append(f"{stem}: column {col!r} retyped {typ} -> {n['fields'][col]}")
        for col in n["fields"]:
            if col not in o["fields"]:
                diff.additive.append(f"{stem}: new column {col!r}")
    for stem in sorted(set(b) - set(a)):
        diff.additive.append(f"{stem}: new dataset")
    return diff
