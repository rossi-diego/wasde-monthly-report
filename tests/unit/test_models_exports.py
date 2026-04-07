# tests/unit/test_models_exports.py
"""Tests for export data models."""

from __future__ import annotations

from datetime import date

from wasde.models.exports import ExportPaceResponse, ExportRecord


def test_export_record_strips_whitespace():
    rec = ExportRecord(
        week_ending=date(2024, 1, 5),
        commodity="  Soybeans  ",
        destination="  China  ",
        net_sales_mt=100.0,
        cumulative_exports_mt=500.0,
    )
    assert rec.commodity == "Soybeans"
    assert rec.destination == "China"


def test_export_pace_response():
    resp = ExportPaceResponse(
        commodity="Soybeans",
        marketing_year=2024,
        cumulative_exports_mt=30_000_000,
        usda_target_mt=50_000_000,
        pace_pct=60.0,
        as_of_date=date(2025, 3, 1),
    )
    assert resp.pace_pct == 60.0
    assert resp.usda_target_mt == 50_000_000


def test_export_pace_nullable_fields():
    resp = ExportPaceResponse(
        commodity="Corn",
        marketing_year=2024,
        cumulative_exports_mt=10_000_000,
        usda_target_mt=None,
        pace_pct=None,
        as_of_date=date(2025, 3, 1),
    )
    assert resp.usda_target_mt is None
    assert resp.pace_pct is None
