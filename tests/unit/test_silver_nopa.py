# tests/unit/test_silver_nopa.py
from __future__ import annotations

from datetime import date

from wasde.pipelines.bronze.nopa import _parse_nopa_date


def test_parse_nopa_date_short_format():
    result = _parse_nopa_date("Jan-25")
    assert result == date(2025, 1, 1)


def test_parse_nopa_date_long_format():
    result = _parse_nopa_date("January 2025")
    assert result == date(2025, 1, 1)


def test_parse_nopa_date_slash_format():
    result = _parse_nopa_date("01/2025")
    assert result == date(2025, 1, 1)


def test_parse_nopa_date_invalid_returns_none():
    result = _parse_nopa_date("not a date")
    assert result is None


def test_parse_nopa_date_empty_returns_none():
    result = _parse_nopa_date("")
    assert result is None
