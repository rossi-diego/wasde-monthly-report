# tests/unit/test_silver_psd.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from wasde.pipelines.silver.psd import _normalise_row


def test_normalise_row_with_release_date():
    raw = {
        "releaseDate": "2024-05-10",
        "_commodity_name": "Soybeans",
        "countryName": "World",
        "marketYear": 2024,
        "attributeName": "Ending Stocks",
        "value": 112.5,
        "unitDescription": "1000 MT",
    }
    result = _normalise_row(raw)
    assert result["report_date"] == date(2024, 5, 10)
    assert result["commodity"] == "Soybeans"
    assert result["country"] == "World"
    assert result["marketing_year"] == 2024
    assert result["attribute"] == "Ending Stocks"
    assert result["value"] == 112.5
    assert result["unit"] == "1000 MT"


def test_normalise_row_missing_date_defaults_to_today():
    raw = {
        "releaseDate": None,
        "_commodity_name": "Corn",
        "countryName": "United States",
        "marketYear": 2023,
        "attributeName": "Production",
        "value": 350.0,
        "unitDescription": "1000 MT",
    }
    result = _normalise_row(raw)
    assert result["report_date"] == date.today()


def test_normalise_row_empty_fields():
    raw = {}
    result = _normalise_row(raw)
    assert result["commodity"] == ""
    assert result["country"] == ""
    assert result["value"] is None
