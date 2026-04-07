# tests/unit/test_downloads.py
"""Tests for CSV/XLSX download helper."""

from __future__ import annotations

from wasde.api.download import stream_download


def test_csv_download_headers():
    """stream_download with fmt='csv' sets correct headers."""
    data = [
        {"commodity": "Soybeans", "value": 100.5},
        {"commodity": "Corn", "value": 200.3},
    ]
    response = stream_download(data, filename="test_data", fmt="csv")

    assert response.media_type == "text/csv"
    assert "test_data.csv" in response.headers["content-disposition"]


def test_xlsx_download_headers():
    """stream_download with fmt='xlsx' sets correct headers."""
    data = [{"a": 1, "b": 2}]
    response = stream_download(data, filename="test_xlsx", fmt="xlsx")

    assert "spreadsheetml" in response.media_type
    assert "test_xlsx.xlsx" in response.headers["content-disposition"]


def test_csv_download_empty_data():
    """Empty data should still return a valid CSV response."""
    response = stream_download([], filename="empty", fmt="csv")
    assert response.media_type == "text/csv"


def test_stream_download_from_dataframe_input():
    """stream_download works with list of dicts (simulating fetchall)."""
    data = [{"x": i, "y": i * 2} for i in range(5)]
    response = stream_download(data, filename="series", fmt="csv")
    assert response.status_code == 200
