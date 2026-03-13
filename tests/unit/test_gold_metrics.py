# tests/unit/test_gold_metrics.py
"""Tests for Gold layer SQL logic using in-memory DuckDB."""
from __future__ import annotations

import duckdb
import pandas as pd
import pytest
from datetime import date


def test_stock_to_use_calculation():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE test_psd AS
        SELECT
            '2024-05-01'::DATE AS report_date,
            'Soybeans' AS commodity,
            'World' AS country,
            2024 AS marketing_year,
            '1000 MT' AS unit,
            3800.0 AS ending_stocks,
            35000.0 AS domestic_total,
            NULL AS production,
            NULL AS imports,
            NULL AS exports,
            NULL AS beginning_stocks
    """)

    result = con.execute("""
        SELECT
            ROUND(ending_stocks / domestic_total * 100, 2) AS stu
        FROM test_psd
        WHERE domestic_total > 0
    """).fetchone()

    assert result is not None
    assert abs(result[0] - 10.86) < 0.01
    con.close()


def test_revision_tracking_window_function():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE revisions AS
        SELECT * FROM (VALUES
            ('2024-03-01'::DATE, 'Soybeans', 'World', 2024, 110.0),
            ('2024-04-01'::DATE, 'Soybeans', 'World', 2024, 108.0),
            ('2024-05-01'::DATE, 'Soybeans', 'World', 2024, 115.0)
        ) t(report_date, commodity, country, marketing_year, ending_stocks)
    """)

    rows = con.execute("""
        SELECT
            report_date,
            ending_stocks - LAG(ending_stocks) OVER (
                PARTITION BY commodity, country, marketing_year
                ORDER BY report_date
            ) AS revision
        FROM revisions
        ORDER BY report_date
    """).fetchall()

    assert rows[0][1] is None       # first row has no previous
    assert rows[1][1] == -2.0       # 108 - 110 = -2
    assert rows[2][1] == 7.0        # 115 - 108 = 7
    con.close()
