# src/wasde/pipelines/bronze/psd.py
"""Bronze layer — USDA FAS PSD API extractor.

Fetches raw supply & demand data for 5 commodities and saves it
as a dated Parquet file in data/bronze/psd/.  The raw JSON is
preserved exactly as received — no transformations here.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

PSD_BASE_URL = "https://api.fas.usda.gov/api/psd"

COMMODITY_CODES: dict[str, str] = {
    "Wheat": "0410000",
    "Corn": "0440000",
    "Soybeans": "2222000",
    "Soybean Meal": "2223000",
    "Soybean Oil": "4243000",
}


def _fetch_commodity(api_key: str, commodity_code: str) -> list[dict]:
    """Fetch all PSD records for one commodity from the USDA FAS API."""
    url = f"{PSD_BASE_URL}/commodity/data"
    params: dict[str, str] = {
        "commodityCode": commodity_code,
        "API_KEY": api_key,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Fetched %d records for commodity code %s", len(data), commodity_code)
    return list(data)


def extract_psd(
    api_key: str, run_date: date | None = None, output_dir: Path | None = None
) -> Path:
    """Fetch all 5 commodities from PSD API and save raw Parquet.

    Args:
        api_key: USDA api.data.gov key.
        run_date: Date tag for the output filename (defaults to today).
        output_dir: Directory for bronze Parquet files.

    Returns:
        Path to the written Parquet file.
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
        except requests.HTTPError as exc:
            logger.error("Failed to fetch %s (%s): %s", commodity_name, code, exc)

    if not all_records:
        raise RuntimeError("No data fetched from PSD API — check your API key.")

    df = pd.DataFrame(all_records)
    df.to_parquet(output_path, index=False)
    logger.info("Bronze PSD saved: %s (%d rows)", output_path, len(df))
    return output_path
