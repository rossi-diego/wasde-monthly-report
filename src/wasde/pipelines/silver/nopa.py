# src/wasde/pipelines/silver/nopa.py
"""Silver layer — NOPA crush data validation and cleaning."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from wasde.models.nopa import NOPARecord

logger = logging.getLogger(__name__)

# Column name patterns to look for (NOPA table headers vary)
CRUSH_COLUMNS = ["soybean crush", "crush", "soybeans crushed"]
OIL_COLUMNS = ["soybean oil stocks", "oil stocks", "soy oil"]


def _find_column(df: pd.DataFrame, patterns: list[str]) -> str | None:
    for col in df.columns:
        if any(p in col.lower() for p in patterns):
            return col
    return None


def transform_nopa(bronze_path: Path, silver_path: Path) -> int:
    df_raw = pd.read_parquet(bronze_path)
    crush_col = _find_column(df_raw, CRUSH_COLUMNS)
    oil_col = _find_column(df_raw, OIL_COLUMNS)

    if crush_col is None or oil_col is None:
        logger.error(
            "Could not identify crush/oil columns in NOPA data. Columns: %s",
            list(df_raw.columns),
        )
        return 0

    valid_rows: list[dict] = []
    invalid_count = 0

    for _, row in df_raw.iterrows():
        try:
            record = NOPARecord(
                report_date=row["report_date"],
                crush_million_bu=row[crush_col],
                oil_stocks_million_lbs=row[oil_col],
            )
            valid_rows.append(record.model_dump())
        except (ValidationError, KeyError, ValueError) as exc:
            invalid_count += 1
            logger.debug("Invalid NOPA row skipped: %s", exc)

    if invalid_count:
        logger.warning("Dropped %d invalid NOPA rows", invalid_count)

    if not valid_rows:
        return 0

    df_new = pd.DataFrame(valid_rows)

    if silver_path.exists():
        df_existing = pd.read_parquet(silver_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        silver_path.parent.mkdir(parents=True, exist_ok=True)
        df_combined = df_new

    df_combined = df_combined.drop_duplicates(subset=["report_date"], keep="last")
    df_combined = df_combined.sort_values("report_date")
    df_combined.to_parquet(silver_path, index=False)
    logger.info("Silver NOPA written: %s (%d rows)", silver_path, len(df_combined))
    return len(df_new)
