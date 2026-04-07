# tests/unit/test_silver_exports.py
"""Tests for silver exports normalisation logic."""

from __future__ import annotations

from wasde.pipelines.silver.exports import _normalise_row


def test_normalise_row_standard_keys():
    raw = {
        "weekEndingDate": "2025-01-03",
        "_commodity_name": "Soybeans",
        "countryName": "China",
        "netSalesMT": 150000.0,
        "cumulativeExportsMT": 2000000.0,
    }
    result = _normalise_row(raw)
    assert result["week_ending"] == "2025-01-03"
    assert result["commodity"] == "Soybeans"
    assert result["destination"] == "China"
    assert result["net_sales_mt"] == 150000.0


def test_normalise_row_alternate_keys():
    raw = {
        "weekEnding": "2025-01-10",
        "commodityName": "Corn",
        "country": "Japan",
        "netSales": 80000.0,
        "cumulativeExports": 1500000.0,
    }
    result = _normalise_row(raw)
    assert result["week_ending"] == "2025-01-10"
    assert result["commodity"] == "Corn"
    assert result["net_sales_mt"] == 80000.0


def test_normalise_row_missing_fields():
    raw = {}
    result = _normalise_row(raw)
    assert result["commodity"] == ""
    assert result["net_sales_mt"] == 0.0
    assert result["cumulative_exports_mt"] == 0.0
