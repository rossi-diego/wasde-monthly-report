# src/wasde/pipelines/bronze/exports.py
"""Bronze layer — USDA FAS Export Sales Reporting (ESR) extractor.

Uses the FAS OpenData ESR API (same base as PSD).
Requires API_KEY header from https://api.data.gov/signup/

API docs: https://apps.fas.usda.gov/opendata/swagger/ui/index
Old esrquery URL (dead as of Apr 2026) → new OpenData endpoint.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# New FAS OpenData ESR base URL
ESR_BASE_URL = "https://apps.fas.usda.gov/OpenData/api/esr"

# ESR commodity codes
ESR_COMMODITY_CODES: dict[str, str] = {
    "Soybeans": "108",
    "Corn": "101",
    "Wheat": "104",
    "Soybean Meal": "107",
    "Soybean Oil": "106",
}

# Marketing year start months
MARKETING_YEAR_START: dict[str, int] = {
    "Soybeans": 9,
    "Corn": 9,
    "Wheat": 6,
    "Soybean Meal": 10,
    "Soybean Oil": 10,
}


def _fetch_esr_commodity(
    api_key: str, commodity_code: str, market_year: int
) -> list[dict]:
    """Fetch weekly export sales for one commodity from the OpenData ESR API."""
    url = (
        f"{ESR_BASE_URL}/exports/commodityCode/{commodity_code}"
        f"/allCountries/marketYear/{market_year}"
    )
    headers = {"API_KEY": api_key}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("data", [])


def extract_exports(
    run_date: date | None = None,
    output_dir: Path | None = None,
    market_year: int | None = None,
) -> Path | None:
    """Fetch current marketing year export sales for all commodities.

    Uses the USDA_PSD_KEY env var for authentication (same key as PSD).
    Returns None if extraction fails completely.
    """
    api_key = os.environ.get("USDA_PSD_KEY", "")
    if not api_key:
        logger.warning("Skipping exports — USDA_PSD_KEY not set")
        return None

    if run_date is None:
        run_date = date.today()
    if output_dir is None:
        output_dir = Path("data/bronze/exports")
    if market_year is None:
        market_year = run_date.year if run_date.month >= 9 else run_date.year - 1

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"exports_{run_date}.parquet"

    all_records: list[dict] = []
    for commodity_name, code in ESR_COMMODITY_CODES.items():
        try:
            records = _fetch_esr_commodity(api_key, code, market_year)
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
            logger.warning("Failed to fetch ESR for %s: %s", commodity_name, exc)

    if not all_records:
        logger.warning("No ESR data fetched — API may be unavailable")
        return None

    df = pd.DataFrame(all_records)
    df.to_parquet(output_path, index=False)
    logger.info("Bronze exports saved: %s (%d rows)", output_path, len(df))
    return output_path
