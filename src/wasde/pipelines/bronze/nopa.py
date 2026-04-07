# src/wasde/pipelines/bronze/nopa.py
"""Bronze layer — NOPA monthly crush report scraper.

Scrapes the HTML table from nopa.org/resources/crush-report/
and saves raw data as a dated Parquet file.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from lxml import html

logger = logging.getLogger(__name__)

NOPA_URL = "https://www.nopa.org/resources/crush-report/"


def _parse_nopa_table(page_content: bytes) -> pd.DataFrame:
    """Parse the NOPA monthly crush HTML table into a DataFrame."""
    tree = html.fromstring(page_content)
    tables = tree.xpath("//table")
    if not tables:
        raise ValueError("No HTML table found on NOPA crush report page.")

    rows: list[dict] = []
    for table in tables:
        headers = [th.text_content().strip() for th in table.xpath(".//th")]
        if not any("crush" in h.lower() for h in headers):
            continue

        for tr in table.xpath(".//tr")[1:]:
            cells = [td.text_content().strip() for td in tr.xpath(".//td")]
            if len(cells) < 2:
                continue

            raw_date = cells[0]
            # Normalise date formats: "Jan-25", "January 2025", "01/2025"
            parsed_date = _parse_nopa_date(raw_date)
            if parsed_date is None:
                continue

            row: dict[str, object] = {"report_date": parsed_date.isoformat()}
            for i, header in enumerate(headers[1:], start=1):
                if i < len(cells):
                    row[header] = cells[i]
            rows.append(row)
        break  # only process the first matching table

    return pd.DataFrame(rows)


def _parse_nopa_date(raw: str) -> date | None:
    """Try common date formats used on the NOPA page."""
    raw = raw.strip()
    for fmt in ("%b-%y", "%B %Y", "%m/%Y", "%b %Y"):
        try:
            import datetime

            return datetime.datetime.strptime(raw, fmt).date().replace(day=1)
        except ValueError:
            continue
    logger.warning("Could not parse NOPA date: %r", raw)
    return None


def extract_nopa(run_date: date | None = None, output_dir: Path | None = None) -> Path:
    """Scrape NOPA crush report page and save raw Parquet.

    Args:
        run_date: Date tag for the output filename (defaults to today).
        output_dir: Directory for bronze Parquet files.

    Returns:
        Path to the written Parquet file.
    """
    if run_date is None:
        run_date = date.today()
    if output_dir is None:
        output_dir = Path("data/bronze/nopa")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"nopa_{run_date}.parquet"

    resp = requests.get(NOPA_URL, timeout=30)
    resp.raise_for_status()

    df = _parse_nopa_table(resp.content)
    if df.empty:
        raise RuntimeError(
            "NOPA scraper returned no rows — page structure may have changed."
        )

    df.to_parquet(output_path, index=False)
    logger.info("Bronze NOPA saved: %s (%d rows)", output_path, len(df))
    return output_path
