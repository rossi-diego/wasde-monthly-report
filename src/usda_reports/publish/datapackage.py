"""``datapackage.json`` (Frictionless Data Package v1) generated from the dbt manifest.

Each catalogue file is one resource: path, format, mediatype, bytes, ``hash`` (sha256), rows,
temporal coverage, latest release key, schema version, licence and a Table Schema. Field
names and types are read from the written Parquet file itself; descriptions come from the dbt
``manifest.json`` (i.e. the models' ``schema.yml``), so the published dictionary cannot drift
from the models. Fields a model does not document get the model description's column-less
default (an empty string), never invented text.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from usda_reports.core.registry import Registry
from usda_reports.publish.catalogue import ALL_DATASETS, Dataset

PROFILE = "tabular-data-package"
# The tabular package profile requires every resource to declare the tabular resource profile.
RESOURCE_PROFILE = "tabular-data-resource"
MEDIATYPE = {"parquet": "application/vnd.apache.parquet", "csv": "text/csv"}

# DuckDB → Table Schema field types.
_TYPES = {
    "VARCHAR": "string",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "DOUBLE": "number",
    "FLOAT": "number",
    "DECIMAL": "number",
    "INTEGER": "integer",
    "BIGINT": "integer",
    "SMALLINT": "integer",
    "TINYINT": "integer",
    "HUGEINT": "integer",
    "UINTEGER": "integer",
    "UBIGINT": "integer",
    "TIMESTAMP": "datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime",
}


def field_type(duck_type: str) -> str:
    t = duck_type.upper()
    if t.startswith("DECIMAL"):
        return "number"
    return _TYPES.get(t, "any")


def dbt_models(manifest_path: Path) -> dict[str, dict[str, Any]]:
    """model name → {description, columns{name: description}} from dbt's manifest.json."""
    if not manifest_path.exists():
        return {}
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for node in raw.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        out[node["name"]] = {
            "description": node.get("description") or "",
            "columns": {
                name: (col.get("description") or "")
                for name, col in (node.get("columns") or {}).items()
            },
            "contract": bool((node.get("contract") or {}).get("enforced")),
        }
    return out


def table_schema(
    con: duckdb.DuckDBPyConnection, parquet: Path, docs: dict[str, str]
) -> dict[str, Any]:
    cols = con.execute(f"describe select * from read_parquet('{parquet.as_posix()}')").fetchall()
    return {
        "fields": [
            {"name": name, "type": field_type(str(typ)), "description": docs.get(name, "")}
            for name, typ, *_ in cols
        ]
    }


def build_datapackage(
    entries: list[dict[str, Any]],
    pub_dir: Path,
    manifest_path: Path,
    registry: Registry,
    tag: str | None,
    repo: str,
    datasets: list[Dataset] | None = None,
) -> dict[str, Any]:
    models = dbt_models(manifest_path)
    by_stem = {d.stem: d for d in (datasets or ALL_DATASETS)}
    con = duckdb.connect()
    resources = []
    schemas: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.get("legacy_alias_of"):
            continue
        stem = e["file"].split(".", 1)[0]
        ds = by_stem.get(stem)
        if ds is None:
            continue
        if stem not in schemas:
            pq = pub_dir / f"{stem}.parquet"
            schemas[stem] = table_schema(con, pq, models.get(ds.model, {}).get("columns", {}))
        cfg = registry.reports.get(ds.report_id)
        licence = ds.licence or (
            cfg.licence
            if cfg
            else "US Government work, public domain; cite USDA FAS and USDA OCE/WAOB"
        )
        fmt = e["format"]
        res: dict[str, Any] = {
            "profile": RESOURCE_PROFILE,
            "name": e["file"].replace(".", "_").replace("-", "_").lower(),
            "path": e["file"],
            "title": f"{stem} ({fmt})",
            "description": ds.description,
            "format": "csv" if fmt == "csv" else "parquet",
            "mediatype": MEDIATYPE[fmt],
            "encoding": "utf-8" if fmt == "csv" else None,
            "compression": "gz" if e["file"].endswith(".gz") else None,
            "bytes": e["bytes"],
            "hash": f"sha256:{e['sha256']}",
            "rows": e["rows"],
            "report_id": ds.report_id,
            "dataset": ds.dataset,
            "schema_version": ds.major,
            "dbt_model": ds.model,
            "contract_enforced": models.get(ds.model, {}).get("contract", False),
            "temporal_coverage": e.get("coverage"),
            "latest_release_key": e.get("latest_release_key"),
            "licenses": [{"name": "public-domain", "title": licence}],
            "release_url": (
                f"https://github.com/{repo}/releases/download/{tag}/{e['file']}" if tag else None
            ),
            "schema": schemas[stem],
        }
        resources.append({k: v for k, v in res.items() if v is not None})
    con.close()
    return {
        "profile": PROFILE,
        "name": "usda-reports",
        "title": "USDA Reports Dashboard: harmonized WASDE, Export Sales and NASS crush data",
        "version": tag or "unreleased",
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "homepage": f"https://github.com/{repo}",
        "licenses": [
            {
                "name": "public-domain",
                "title": "US Government work, public domain; cite the USDA agency per resource",
            }
        ],
        "sources": [
            {"title": "USDA OCE/WAOB: WASDE", "path": "https://www.usda.gov/oce/commodity/wasde"},
            {
                "title": "USDA FAS: Export Sales Reporting (ESR) API",
                "path": "https://api.fas.usda.gov",
            },
            {
                "title": "USDA NASS: Fats & Oils (Oilseed Crushings, Production, Consumption "
                "and Stocks), via ESMIS",
                "path": "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/FatsOils",
            },
        ],
        "resources": resources,
    }


def write_datapackage(doc: dict[str, Any], path: Path) -> Path:
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
