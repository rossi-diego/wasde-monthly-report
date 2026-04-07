# src/wasde/pipelines/silver/exports.py
"""Silver layer — USDA ESR export sales validation and cleaning."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from wasde.models.exports import ExportRecord

logger = logging.getLogger(__name__)


def _normalise_row(raw: dict) -> dict:
    return {
        "week_ending": raw.get("weekEndingDate")
        or raw.get("weeklyExportDate")
        or raw.get("weekEnding"),
        "commodity": raw.get("_commodity_name") or raw.get("commodityName", ""),
        "destination": raw.get("countryName") or raw.get("country", ""),
        "net_sales_mt": raw.get("netSalesMT") or raw.get("netSales") or 0.0,
        "cumulative_exports_mt": raw.get("cumulativeExportsMT")
        or raw.get("cumulativeExports")
        or 0.0,
    }


def transform_exports(bronze_path: Path, silver_path: Path) -> int:
    df_raw = pd.read_parquet(bronze_path)
    if df_raw.empty:
        logger.warning("Empty Bronze exports file: %s", bronze_path)
        return 0

    valid_rows: list[dict] = []
    invalid_count = 0

    for _, row in df_raw.iterrows():
        normalised = _normalise_row(row.to_dict())
        try:
            record = ExportRecord(**normalised)
            valid_rows.append(record.model_dump())
        except (ValidationError, ValueError) as exc:
            invalid_count += 1
            logger.debug("Invalid export row skipped: %s", exc)

    if invalid_count:
        logger.warning("Dropped %d invalid export rows", invalid_count)

    if not valid_rows:
        return 0

    df_new = pd.DataFrame(valid_rows)

    if silver_path.exists():
        df_existing = pd.read_parquet(silver_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        silver_path.parent.mkdir(parents=True, exist_ok=True)
        df_combined = df_new

    key_cols = ["week_ending", "commodity", "destination"]
    df_combined = df_combined.drop_duplicates(subset=key_cols, keep="last")
    df_combined.to_parquet(silver_path, index=False)
    logger.info("Silver exports written: %s (%d rows)", silver_path, len(df_combined))
    return len(df_new)
