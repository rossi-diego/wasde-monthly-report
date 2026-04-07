# src/wasde/pipelines/bronze/exports.py
"""Bronze layer — USDA FAS Export Sales Reporting (ESR) extractor.

The ESR API requires no authentication.  We fetch weekly cumulative
export sales for the same 5 commodities as PSD.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

ESR_BASE_URL = "https://apps.fas.usda.gov/esrquery/esrq.aspx"

# ESR commodity codes (different from PSD codes)
ESR_COMMODITY_CODES: dict[str, str] = {
    "Soybeans": "2222000",
    "Corn": "0440000",
    "Wheat": "0410000",
    "Soybean Meal": "2223000",
    "Soybean Oil": "4243000",
}

# Marketing year start months (used to filter the right year's data)
MARKETING_YEAR_START: dict[str, int] = {
    "Soybeans": 9,  # Sep 1
    "Corn": 9,  # Sep 1
    "Wheat": 6,  # Jun 1
    "Soybean Meal": 10,  # Oct 1
    "Soybean Oil": 10,  # Oct 1
}


def _fetch_esr_commodity(commodity_code: str, market_year: int) -> list[dict]:
    """Fetch weekly export sales for one commodity and marketing year."""
    params = {
        "type": "weekly",
        "commodity": commodity_code,
        "marketYear": str(market_year),
        "format": "json",
    }
    resp = requests.get(ESR_BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("data", [])


def extract_exports(
    run_date: date | None = None,
    output_dir: Path | None = None,
    market_year: int | None = None,
) -> Path:
    """Fetch current marketing year export sales for all commodities.

    Args:
        run_date: Date tag for the output filename (defaults to today).
        output_dir: Directory for bronze Parquet files.
        market_year: Marketing year to fetch (defaults to current year).

    Returns:
        Path to the written Parquet file.
    """
    if run_date is None:
        run_date = date.today()
    if output_dir is None:
        output_dir = Path("data/bronze/exports")
    if market_year is None:
        # Soybean marketing year starts Sep 1; use previous year Aug and before
        market_year = run_date.year if run_date.month >= 9 else run_date.year - 1

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"exports_{run_date}.parquet"

    all_records: list[dict] = []
    for commodity_name, code in ESR_COMMODITY_CODES.items():
        try:
            records = _fetch_esr_commodity(code, market_year)
            for r in records:
                r["_commodity_name"] = commodity_name
                r["_market_year"] = market_year
            all_records.extend(records)
            logger.info(
                "Fetched %d ESR records for %s MY%d",
                len(records),
                commodity_name,
                market_year,
            )
        except Exception as exc:
            logger.error("Failed to fetch ESR for %s: %s", commodity_name, exc)

    if not all_records:
        logger.warning("No ESR data fetched — ESR API may be unavailable.")
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(all_records)

    df.to_parquet(output_path, index=False)
    logger.info("Bronze exports saved: %s (%d rows)", output_path, len(df))
    return output_path
