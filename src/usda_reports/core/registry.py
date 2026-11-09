"""Report registry: ``config/reports.yaml`` → typed :class:`ReportConfig` and spec instances."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from usda_reports.core.config import Settings
    from usda_reports.reports.base import ReportSpec


class ReportConfig(BaseModel):
    id: str
    enabled: bool = False
    title: str
    agency: str
    cadence: Literal["weekly", "monthly", "quarterly"]
    release_time_et: str = "12:00"
    window_h: int = 6
    grace_days: int = 45
    key_env: str | None = None
    licence: str
    min_rows: int = 0
    history_start: str | None = None
    # month = YYYY-MM keys (WASDE); date = YYYY-MM-DD keys (weekly reports, NASS monthly
    # reports whose release month can hold two releases after a shutdown).
    release_key_format: Literal["month", "date"] = "month"
    spec: str | None = None  # "package.module:ClassName"

    @property
    def cadence_days(self) -> int:
        return {"weekly": 7, "monthly": 31, "quarterly": 92}[self.cadence]


class Registry(BaseModel):
    reports: dict[str, ReportConfig] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Registry:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            reports={rid: ReportConfig(id=rid, **cfg) for rid, cfg in raw["reports"].items()}
        )

    def get(self, report_id: str) -> ReportConfig:
        try:
            return self.reports[report_id]
        except KeyError as exc:
            raise KeyError(f"unknown report_id {report_id!r} (see config/reports.yaml)") from exc

    def enabled(self) -> list[ReportConfig]:
        return [r for r in self.reports.values() if r.enabled]

    def spec(self, report_id: str, settings: Settings) -> ReportSpec:
        cfg = self.get(report_id)
        if not cfg.spec:
            raise ValueError(f"report {report_id!r} has no spec implementation yet")
        module, _, name = cfg.spec.partition(":")
        cls_ = getattr(importlib.import_module(module), name)
        spec: ReportSpec = cls_(settings, cfg)
        return spec

    def enabled_specs(self, settings: Settings) -> list[ReportSpec]:
        return [self.spec(r.id, settings) for r in self.enabled()]


def load_registry(config_dir: Path) -> Registry:
    return Registry.load(config_dir / "reports.yaml")
