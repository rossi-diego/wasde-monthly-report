"""Silver driver: full reparse of every enabled report (no correctness depends on cache)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest
from usda_reports.core.registry import load_registry

log = get_logger(__name__)


@dataclass
class SilverResult:
    rows: dict[str, int] = field(default_factory=dict)
    seconds: dict[str, float] = field(default_factory=dict)
    alerts: dict[str, list[str]] = field(default_factory=dict)


def build_all(settings: Settings, manifest: Manifest, only: str | None = None) -> SilverResult:
    """Build ``data/silver/<report_id>.parquet`` for every enabled report (or just ``only``)."""
    result = SilverResult()
    registry = load_registry(settings.config_dir)
    for spec in registry.enabled_specs(settings):
        if only and spec.report_id != only:
            continue
        t0 = time.perf_counter()
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
