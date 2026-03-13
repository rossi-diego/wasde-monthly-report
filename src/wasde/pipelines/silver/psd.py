# src/wasde/pipelines/silver/psd.py
"""Silver layer — PSD data validation and cleaning.

Reads Bronze PSD Parquet, validates each row with Pydantic,
drops invalid rows (logged), and appends clean rows to the
cumulative Silver Parquet (deduped by natural key).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from wasde.models.psd import PSDRecord

logger = logging.getLogger(__name__)

# PSD API attribute name → clean column name
ATTRIBUTE_MAP: dict[str, str] = {
    "Beginning Stocks": "beginning_stocks",
    "Production": "production",
    "Imports": "imports",
    "Dom. Consumption": "domestic_total",
    "Exports": "exports",
    "Ending Stocks": "ending_stocks",
}

# PSD API field names (vary slightly across commodities)
PSD_FIELDS = {
    "report_date": ["marketingYearLabel", "releaseDate"],
    "commodity": ["_commodity_name", "commodityName"],
    "country": ["countryName"],
    "marketing_year": ["marketYear"],
    "attribute": ["attributeName"],
    "value": ["value"],
    "unit": ["unitDescription"],
}


def _normalise_row(raw: dict) -> dict:
    """Map PSD API field names to our canonical schema."""

    def pick(keys: list[str]) -> object:
        for k in keys:
            if k in raw and raw[k] is not None:
                return raw[k]
        return None

    # Report date: use releaseDate if available
    import datetime
    raw_date = pick(["releaseDate", "marketingYearLabel"])
    try:
        report_date = datetime.date.fromisoformat(str(raw_date)[:10])
    except (ValueError, TypeError):
        report_date = datetime.date.today()

    return {
        "report_date": report_date,
        "commodity": pick(["_commodity_name", "commodityName"]) or "",
        "country": pick(["countryName"]) or "",
        "marketing_year": pick(["marketYear"]) or 0,
        "attribute": pick(["attributeName"]) or "",
        "value": pick(["value"]),
        "unit": pick(["unitDescription"]) or "",
    }


def transform_psd(bronze_path: Path, silver_path: Path) -> int:
    """Validate + clean PSD Bronze. Append to Silver Parquet.

    Args:
        bronze_path: Input Bronze Parquet file.
        silver_path: Output Silver Parquet file (appended/created).

    Returns:
        Number of valid rows written.
    """
    df_raw = pd.read_parquet(bronze_path)
    valid_rows: list[dict] = []
    invalid_count = 0

    for _, row in df_raw.iterrows():
        normalised = _normalise_row(row.to_dict())
        try:
            record = PSDRecord(**normalised)
            valid_rows.append(record.model_dump())
        except ValidationError as exc:
            invalid_count += 1
            logger.debug("Invalid PSD row skipped: %s", exc)

    if invalid_count:
        logger.warning("Dropped %d invalid PSD rows out of %d", invalid_count, len(df_raw))

    if not valid_rows:
        logger.error("No valid rows after PSD validation — check Bronze data.")
        return 0

    df_new = pd.DataFrame(valid_rows)

    # Append to existing Silver, dedup by natural key
    if silver_path.exists():
        df_existing = pd.read_parquet(silver_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        silver_path.parent.mkdir(parents=True, exist_ok=True)
        df_combined = df_new

    key_cols = ["report_date", "commodity", "country", "marketing_year", "attribute"]
    df_combined = df_combined.drop_duplicates(subset=key_cols, keep="last")
    df_combined.to_parquet(silver_path, index=False)
    logger.info("Silver PSD written: %s (%d rows total)", silver_path, len(df_combined))
    return len(df_new)
