# src/wasde/pipelines/bronze/psd.py
"""Bronze layer — USDA FAS PSD API extractor.

Fetches raw supply & demand data for 5 commodities from the
FAS OpenData API and saves as a dated Parquet file.

API docs: https://apps.fas.usda.gov/opendata/swagger/ui/index
Auth: API_KEY header from https://api.data.gov/signup/
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# New FAS OpenData base URL (old api.fas.usda.gov/api/psd is dead)
PSD_BASE_URL = "https://apps.fas.usda.gov/OpenData/api/psd"

COMMODITY_CODES: dict[str, str] = {
    "Wheat": "0410000",
    "Corn": "0440000",
    "Soybeans": "2222000",
    "Soybean Meal": "2223000",
    "Soybean Oil": "4243000",
}

# Recent market years to fetch (keeps payload manageable)
MARKET_YEARS = list(range(2020, date.today().year + 2))


def _fetch_commodity(api_key: str, commodity_code: str) -> list[dict]:
    """Fetch PSD records for one commodity from the FAS OpenData API."""
    headers = {"API_KEY": api_key}
    all_records: list[dict] = []

    for year in MARKET_YEARS:
        url = f"{PSD_BASE_URL}/commodity/{commodity_code}/country/all/year/{year}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                all_records.extend(data)
        except requests.HTTPError as exc:
            logger.warning("PSD %s year %d: %s", commodity_code, year, exc)
        except Exception as exc:
            logger.warning(
                "PSD %s year %d unexpected error: %s", commodity_code, year, exc
            )

    logger.info("Fetched %d records for commodity %s", len(all_records), commodity_code)
    return all_records


def extract_psd(
    api_key: str, run_date: date | None = None, output_dir: Path | None = None
) -> Path | None:
    """Fetch all 5 commodities from PSD API and save raw Parquet.

    Returns None if extraction fails completely (graceful degradation).
    """
    if run_date is None:
        run_date = date.today()
    if output_dir is None:
        output_dir = Path("data/bronze/psd")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"psd_{run_date}.parquet"

    all_records: list[dict] = []
    for commodity_name, code in COMMODITY_CODES.items():
        try:
            records = _fetch_commodity(api_key, code)
            for r in records:
                r["_commodity_name"] = commodity_name
            all_records.extend(records)
        except Exception as exc:
            logger.warning("Failed to fetch %s (%s): %s", commodity_name, code, exc)

    if not all_records:
        logger.error(
            "No data fetched from PSD API — check your API key or endpoint status"
        )
        return None

    df = pd.DataFrame(all_records)
    df.to_parquet(output_path, index=False)
    logger.info("Bronze PSD saved: %s (%d rows)", output_path, len(df))
    return output_path
