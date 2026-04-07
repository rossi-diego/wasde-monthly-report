# tests/unit/test_models_nopa.py
"""Tests for NOPA data models."""

from __future__ import annotations

from datetime import date

from wasde.models.nopa import NOPACrushResponse, NOPARecord


def test_nopa_record_parses_string_numbers():
    rec = NOPARecord(
        report_date=date(2025, 1, 15),
        crush_million_bu="196.4",
        oil_stocks_million_lbs="1,845.2",
    )
    assert rec.crush_million_bu == 196.4
    assert rec.oil_stocks_million_lbs == 1845.2


def test_nopa_record_parses_float_numbers():
    rec = NOPARecord(
        report_date=date(2025, 1, 15),
        crush_million_bu=196.4,
        oil_stocks_million_lbs=1845.2,
    )
    assert rec.crush_million_bu == 196.4


def test_nopa_crush_response_nullable_margin():
    resp = NOPACrushResponse(
        report_date=date(2025, 1, 15),
        crush_million_bu=196.4,
        oil_stocks_million_lbs=1845.2,
        crush_margin_usd_per_bu=None,
    )
    assert resp.crush_margin_usd_per_bu is None
