# src/wasde/pipelines/silver/wasde_csv.py
"""Silver layer — WASDE CSV validation and cleaning.

Reads all Bronze WASDE Parquet files, validates each row with Pydantic,
filters out non-S&D rows (reliability projections, empty commodities),
and writes a cumulative Silver Parquet deduped by natural key.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from wasde.models.wasde import WASDERecord

logger = logging.getLogger(__name__)

# Values treated as missing when parsing the Value column
_NULL_VALUES = {"", "-", "NA", "N/A", "nan", "None"}


def _parse_value(raw: object) -> float | None:
    """Convert raw Value string to float, returning None for blanks/sentinels."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s in _NULL_VALUES:
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_marketing_year_start(my: str) -> int | None:
    """Extract start year from marketing year string like '2024/25'."""
    s = str(my).strip()
    if len(s) >= 4:
        try:
            return int(s[:4])
        except ValueError:
            pass
    return None


def _parse_release_date(raw: object) -> date | None:
    """Parse ISO release date string to date."""
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except (ValueError, TypeError):
        return None


def _normalise_row(raw: dict) -> dict | None:
    """Map raw WASDE CSV columns to WASDERecord schema.

    Returns None if the row should be filtered out.
    """
    # Filter: skip reliability projection rows
    reliability = str(raw.get("ReliabilityProjection", "")).strip()
    if reliability:
        return None

    commodity = str(raw.get("Commodity", "")).strip()
    region = str(raw.get("Region", "")).strip()

    # Filter: skip rows with empty commodity or region
    if not commodity or not region:
        return None

    marketing_year = str(raw.get("MarketYear", "")).strip()
    my_start = _parse_marketing_year_start(marketing_year)
    if my_start is None:
        return None

    release_date = _parse_release_date(raw.get("ReleaseDate"))
    if release_date is None:
        return None

    # Parse integer fields
    try:
        wasde_number = int(raw.get("WasdeNumber", 0))
        forecast_year = int(raw.get("ForecastYear", 0))
        forecast_month = int(raw.get("ForecastMonth", 0))
    except (ValueError, TypeError):
        return None

    return {
        "wasde_number": wasde_number,
        "forecast_year": forecast_year,
        "forecast_month": forecast_month,
        "report_title": str(raw.get("ReportTitle", "")).strip(),
        "commodity": commodity,
        "region": region,
        "marketing_year": marketing_year,
        "marketing_year_start": my_start,
        "attribute": str(raw.get("Attribute", "")).strip(),
        "value": _parse_value(raw.get("Value")),
        "unit": str(raw.get("Unit", "")).strip(),
        "release_date": release_date,
        "proj_est_flag": str(raw.get("ProjEstFlag", "")).strip(),
        "annual_quarter_flag": str(raw.get("AnnualQuarterFlag", "")).strip(),
    }


def transform_wasde(bronze_dir: Path, silver_path: Path) -> int:
    """Validate + clean all Bronze WASDE Parquet files into cumulative Silver.

    Args:
        bronze_dir: Directory containing Bronze wasde_*.parquet files.
        silver_path: Output cumulative Silver Parquet file.

    Returns:
        Number of valid rows written.
    """
    parquet_files = sorted(bronze_dir.glob("wasde_*.parquet"))
    if not parquet_files:
        logger.warning("No Bronze WASDE Parquet files found in %s", bronze_dir)
        return 0

    valid_rows: list[dict] = []
    invalid_count = 0
    filtered_count = 0

    for pq_file in parquet_files:
        df_raw = pd.read_parquet(pq_file)
        for _, row in df_raw.iterrows():
            normalised = _normalise_row(row.to_dict())
            if normalised is None:
                filtered_count += 1
                continue

            try:
                record = WASDERecord(**normalised)
                valid_rows.append(record.model_dump())
            except ValidationError as exc:
                invalid_count += 1
                logger.debug("Invalid WASDE row skipped: %s", exc)

    if filtered_count:
        logger.info("Filtered %d non-S&D rows (reliability/empty)", filtered_count)
    if invalid_count:
        logger.warning("Dropped %d invalid WASDE rows", invalid_count)

    if not valid_rows:
        logger.error("No valid rows after WASDE validation — check Bronze data.")
        return 0

    df_new = pd.DataFrame(valid_rows)

    # Deduplicate by natural key
    key_cols = [
        "wasde_number",
        "commodity",
        "region",
        "marketing_year",
        "attribute",
    ]
    df_new = df_new.drop_duplicates(subset=key_cols, keep="last")
    df_new = df_new.sort_values(
        ["commodity", "region", "marketing_year", "forecast_year", "forecast_month"],
    )

    silver_path.parent.mkdir(parents=True, exist_ok=True)
    df_new.to_parquet(silver_path, index=False)
    logger.info("Silver WASDE written: %s (%d rows)", silver_path, len(df_new))
    return len(df_new)
