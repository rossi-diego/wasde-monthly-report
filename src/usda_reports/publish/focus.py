"""Typed access to config/reports/wasde/focus.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class TableRef(BaseModel):
    table: str
    commodity: str


class FocusCommodity(BaseModel):
    label: str
    us: TableRef
    world: TableRef


class Line(BaseModel):
    id: str
    label: str


class HighlightRules(BaseModel):
    max_items: int = 6
    max_per_commodity: int = 2
    attributes: list[str]
    floors: dict[str, dict[str, float]]
    regions: list[str]
    primary_regions: list[str] = []

    def floor(self, scope: str, commodity: str, attribute: str) -> float | None:
        table = self.floors.get(scope, {})
        return table.get(f"{commodity}.{attribute}", table.get(f"default.{attribute}"))


class Focus(BaseModel):
    commodities: dict[str, FocusCommodity]
    regions: list[str]
    balance_lines: list[Line]
    highlights: HighlightRules

    @classmethod
    def load(cls, path: Path) -> Focus:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def tables(self) -> set[str]:
        return {t for c in self.commodities.values() for t in (c.us.table, c.world.table)}
