# tests/unit/test_wasde_csv.py
"""Tests for WASDE CSV ingestion, silver cleaning, and gold SQL logic."""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

# ── Bronze: URL construction ────────────────────────────────────────────────


def test_build_csv_url():
    from wasde.pipelines.bronze.wasde_csv import _build_csv_url

    assert _build_csv_url(2026, 1) == (
        "https://www.usda.gov/sites/default/files/documents/"
        "oce-wasde-report-data-2026-01.csv"
    )
    assert _build_csv_url(2021, 12) == (
        "https://www.usda.gov/sites/default/files/documents/"
        "oce-wasde-report-data-2021-12.csv"
    )


def test_build_csv_url_zero_pads_month():
    from wasde.pipelines.bronze.wasde_csv import _build_csv_url

    url = _build_csv_url(2023, 3)
    assert "-2023-03.csv" in url


# ── Bronze: column validation ───────────────────────────────────────────────


def test_validate_columns_valid():
    from wasde.pipelines.bronze.wasde_csv import WASDE_COLUMNS, _validate_columns

    df = pd.DataFrame(columns=WASDE_COLUMNS)
    assert _validate_columns(df, "test://url") is True


def test_validate_columns_missing():
    from wasde.pipelines.bronze.wasde_csv import _validate_columns

    df = pd.DataFrame(columns=["WasdeNumber", "ReportDate"])
    assert _validate_columns(df, "test://url") is False


def test_validate_columns_extra_columns_ok():
    from wasde.pipelines.bronze.wasde_csv import WASDE_COLUMNS, _validate_columns

    df = pd.DataFrame(columns=[*WASDE_COLUMNS, "ExtraColumn"])
    assert _validate_columns(df, "test://url") is True


# ── Silver: value parsing ───────────────────────────────────────────────────


def test_parse_value_valid():
    from wasde.pipelines.silver.wasde_csv import _parse_value

    assert _parse_value("121.41") == 121.41
    assert _parse_value("1,234.56") == 1234.56
    assert _parse_value("0") == 0.0


def test_parse_value_null_variants():
    from wasde.pipelines.silver.wasde_csv import _parse_value

    assert _parse_value("") is None
    assert _parse_value("-") is None
    assert _parse_value("NA") is None
    assert _parse_value("N/A") is None
    assert _parse_value(None) is None


# ── Silver: marketing year parsing ──────────────────────────────────────────


def test_parse_marketing_year_start():
    from wasde.pipelines.silver.wasde_csv import _parse_marketing_year_start

    assert _parse_marketing_year_start("2024/25") == 2024
    assert _parse_marketing_year_start("2023/24") == 2023
    assert _parse_marketing_year_start("2010/11") == 2010


def test_parse_marketing_year_start_invalid():
    from wasde.pipelines.silver.wasde_csv import _parse_marketing_year_start

    assert _parse_marketing_year_start("") is None
    assert _parse_marketing_year_start("abc") is None
    assert _parse_marketing_year_start("20") is None


# ── Silver: row normalisation ───────────────────────────────────────────────


def _make_raw_row(**overrides) -> dict:
    """Build a realistic raw WASDE CSV row dict."""
    base = {
        "WasdeNumber": "667",
        "ReportDate": "January 2026",
        "ReportTitle": "World and U.S. Supply and Use for Oilseeds",
        "Attribute": "Ending Stocks",
        "ReliabilityProjection": "",
        "Commodity": "Soybeans",
        "Region": "World",
        "MarketYear": "2024/25",
        "ProjEstFlag": "Proj.",
        "AnnualQuarterFlag": "Annual",
        "Value": "121.41",
        "Unit": "Million Metric Tons",
        "ReleaseDate": "2026-01-12",
        "ReleaseTime": "12:00:00.0000000",
        "ForecastYear": "2026",
        "ForecastMonth": "1",
    }
    base.update(overrides)
    return base


def test_normalise_row_valid():
    from wasde.pipelines.silver.wasde_csv import _normalise_row

    result = _normalise_row(_make_raw_row())
    assert result is not None
    assert result["wasde_number"] == 667
    assert result["commodity"] == "Soybeans"
    assert result["marketing_year_start"] == 2024
    assert result["value"] == 121.41
    assert result["release_date"] == date(2026, 1, 12)


def test_normalise_row_filters_reliability():
    from wasde.pipelines.silver.wasde_csv import _normalise_row

    result = _normalise_row(_make_raw_row(ReliabilityProjection="some text"))
    assert result is None


def test_normalise_row_filters_empty_commodity():
    from wasde.pipelines.silver.wasde_csv import _normalise_row

    assert _normalise_row(_make_raw_row(Commodity="")) is None
    assert _normalise_row(_make_raw_row(Region="")) is None


def test_normalise_row_null_value():
    from wasde.pipelines.silver.wasde_csv import _normalise_row

    result = _normalise_row(_make_raw_row(Value="-"))
    assert result is not None
    assert result["value"] is None


# ── Silver: full transform ──────────────────────────────────────────────────


def test_transform_wasde_deduplication(tmp_path):
    from wasde.pipelines.silver.wasde_csv import transform_wasde

    bronze_dir = tmp_path / "bronze"
    bronze_dir.mkdir()

    # Create a Bronze Parquet with duplicate rows
    rows = [_make_raw_row(), _make_raw_row(Value="130.00")]
    df = pd.DataFrame(rows)
    df.to_parquet(bronze_dir / "wasde_2026_01.parquet", index=False)

    silver_path = tmp_path / "silver" / "wasde.parquet"
    count = transform_wasde(bronze_dir, silver_path)

    # Both rows have same natural key — dedup keeps last (130.00)
    assert count == 1
    df_silver = pd.read_parquet(silver_path)
    assert len(df_silver) == 1
    assert df_silver.iloc[0]["value"] == 130.0


def test_transform_wasde_filters_reliability(tmp_path):
    from wasde.pipelines.silver.wasde_csv import transform_wasde

    bronze_dir = tmp_path / "bronze"
    bronze_dir.mkdir()

    rows = [
        _make_raw_row(),
        _make_raw_row(ReliabilityProjection="High", Attribute="Reliability"),
    ]
    df = pd.DataFrame(rows)
    df.to_parquet(bronze_dir / "wasde_2026_01.parquet", index=False)

    silver_path = tmp_path / "silver" / "wasde.parquet"
    count = transform_wasde(bronze_dir, silver_path)

    assert count == 1  # Reliability row filtered out


# ── Gold: revision window functions ─────────────────────────────────────────


def test_gold_wasde_revisions_window():
    """Verify LAG and FIRST_VALUE window logic with sample data."""
    con = duckdb.connect(":memory:")

    # Create sample silver data
    con.execute("""
        CREATE TABLE silver_wasde AS
        SELECT * FROM (VALUES
            ('Soybeans', 'World', '2024/25', 2024, 'Ending Stocks',
             'MMT', 2024, 5, 112.0),
            ('Soybeans', 'World', '2024/25', 2024, 'Ending Stocks',
             'MMT', 2024, 6, 114.5),
            ('Soybeans', 'World', '2024/25', 2024, 'Ending Stocks',
             'MMT', 2024, 7, 111.0)
        ) t(commodity, region, marketing_year, marketing_year_start,
            attribute, unit, forecast_year, forecast_month, value)
    """)

    # Run the same window query used in gold
    rows = con.execute("""
        SELECT
            forecast_month,
            value,
            LAG(value) OVER w AS prev_value,
            value - LAG(value) OVER w AS mom_change,
            FIRST_VALUE(value) OVER w AS first_estimate,
            value - FIRST_VALUE(value) OVER w AS cumulative_revision,
            ROW_NUMBER() OVER w AS revision_number
        FROM silver_wasde
        WINDOW w AS (
            PARTITION BY commodity, region, marketing_year, attribute
            ORDER BY forecast_year, forecast_month
        )
        ORDER BY forecast_month
    """).fetchall()

    # Row 1 (May): first estimate, no previous
    assert rows[0][1] == 112.0  # value
    assert rows[0][2] is None  # prev_value
    assert rows[0][3] is None  # mom_change
    assert rows[0][4] == 112.0  # first_estimate
    assert rows[0][5] == 0.0  # cumulative_revision
    assert rows[0][6] == 1  # revision_number

    # Row 2 (Jun): +2.5 from previous
    assert rows[1][1] == 114.5
    assert rows[1][2] == 112.0
    assert rows[1][3] == 2.5
    assert rows[1][5] == 2.5  # cumulative = 114.5 - 112.0

    # Row 3 (Jul): -3.5 from previous, -1.0 from first
    assert rows[2][1] == 111.0
    assert rows[2][3] == -3.5
    assert rows[2][5] == -1.0  # cumulative = 111.0 - 112.0

    con.close()


def test_gold_wasde_latest_pivot():
    """Verify the pivot + ranking logic for latest S&D values."""
    con = duckdb.connect(":memory:")

    con.execute("""
        CREATE TABLE silver_wasde AS
        SELECT * FROM (VALUES
            ('Soybeans', 'World', '2024/25', 2024, 'Production',
             'MMT', 2024, 5, 400.0),
            ('Soybeans', 'World', '2024/25', 2024, 'Ending Stocks',
             'MMT', 2024, 5, 112.0),
            ('Soybeans', 'World', '2024/25', 2024, 'Production',
             'MMT', 2024, 6, 405.0),
            ('Soybeans', 'World', '2024/25', 2024, 'Ending Stocks',
             'MMT', 2024, 6, 114.5)
        ) t(commodity, region, marketing_year, marketing_year_start,
            attribute, unit, forecast_year, forecast_month, value)
    """)

    rows = con.execute("""
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY commodity, region, marketing_year, attribute
                ORDER BY forecast_year DESC, forecast_month DESC
            ) AS rn
            FROM silver_wasde
            WHERE value IS NOT NULL
        )
        SELECT
            commodity, region, marketing_year,
            forecast_year AS latest_report_year,
            forecast_month AS latest_report_month,
            MAX(CASE WHEN attribute = 'Production' THEN value END) AS production,
            MAX(CASE WHEN attribute = 'Ending Stocks' THEN value END) AS ending_stocks
        FROM ranked
        WHERE rn = 1
        GROUP BY commodity, region, marketing_year,
                 forecast_year, forecast_month
    """).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row[3] == 2024  # latest_report_year
    assert row[4] == 6  # latest_report_month
    assert row[5] == 405.0  # production (from June, the latest)
    assert row[6] == 114.5  # ending_stocks (from June)

    con.close()
