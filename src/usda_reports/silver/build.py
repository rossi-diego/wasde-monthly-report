"""Silver driver: full reparse of every enabled report (no correctness depends on cache).

Reports marked ``isolated`` (Export Sales, oilseed crush) cannot stop the others: when their
full build fails on a known data problem (``spec.source_errors()``: a source error, an unseen
label, a contract break), their
silver is rebuilt from the last good bronze state, the failure is recorded in
``data/silver/build_status.json`` (``build-info`` marks the report ``failed``), and WASDE gold
and publish carry on.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest
from usda_reports.core.registry import load_registry

log = get_logger(__name__)

STATUS_FILE = "build_status.json"


@dataclass
class SilverResult:
    rows: dict[str, int] = field(default_factory=dict)
    seconds: dict[str, float] = field(default_factory=dict)
    alerts: dict[str, list[str]] = field(default_factory=dict)
    # Isolated reports whose full build failed: report_id → error (silver = last good state).
    failed: dict[str, str] = field(default_factory=dict)


def build_all(settings: Settings, manifest: Manifest, only: str | None = None) -> SilverResult:
    """Build ``data/silver/<report_id>.parquet`` for every enabled report (or just ``only``)."""
    result = SilverResult()
    registry = load_registry(settings.config_dir)
    for spec in registry.enabled_specs(settings):
        if only and spec.report_id != only:
            continue
        t0 = time.perf_counter()
        if spec.isolated:
            try:
                silver = spec.build_silver(manifest)
            except spec.source_errors() as exc:
                log.error("silver.report_failed", report=spec.report_id, error=str(exc))
                result.failed[spec.report_id] = str(exc)
                silver = spec.build_silver_last_good(manifest)
        else:
            silver = spec.build_silver(manifest)
        elapsed = time.perf_counter() - t0
        result.rows[spec.report_id] = len(silver)
        result.seconds[spec.report_id] = round(elapsed, 1)
        alerts = spec.silver_alerts(silver)
        if alerts:
            result.alerts[spec.report_id] = alerts
        log.info(
            "silver.timing", report=spec.report_id, rows=len(silver), seconds=round(elapsed, 1)
        )
    return result


def write_status(settings: Settings, result: SilverResult) -> Path:
    """``data/silver/build_status.json``: isolated reports that failed (read by build-info)."""
    path = settings.silver_dir / STATUS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"failed": dict(sorted(result.failed.items())), "rows": result.rows}
    path.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    return path


def failed_reports(settings: Settings) -> set[str]:
    """Report ids recorded as failed by the last silver build (empty when none or no file)."""
    path = settings.silver_dir / STATUS_FILE
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("failed") or {})
