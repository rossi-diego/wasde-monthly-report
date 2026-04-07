# src/wasde/pipelines/bronze/wasde_csv.py
"""Bronze layer — WASDE Historical CSV ingestion.

Downloads monthly WASDE CSV snapshots from the USDA website and saves
each as a dated Parquet file in data/bronze/wasde/.  A JSON manifest
tracks which months have already been ingested so that re-runs are
idempotent.

Data sources:
  - Individual CSVs (2021–current):
      https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-{YYYY}-{MM}.csv
  - Archived ZIPs (2010–2020):
      oce-wasde-report-data-2010-04-to-2015-12.zip
      oce-wasde-report-data-2016-01-to-2020-12.zip
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from wasde.config import settings as default_settings

logger = logging.getLogger(__name__)

# ── Expected CSV schema ─────────────────────────────────────────────────────

WASDE_COLUMNS: list[str] = [
    "WasdeNumber",
    "ReportDate",
    "ReportTitle",
    "Attribute",
    "ReliabilityProjection",
    "Commodity",
    "Region",
    "MarketYear",
    "ProjEstFlag",
    "AnnualQuarterFlag",
    "Value",
    "Unit",
    "ReleaseDate",
    "ReleaseTime",
    "ForecastYear",
    "ForecastMonth",
]

# ── URL patterns ─────────────────────────────────────────────────────────────

WASDE_CSV_URL_TEMPLATE = (
    "https://www.usda.gov/sites/default/files/documents/"
    "oce-wasde-report-data-{year}-{month:02d}.csv"
)

WASDE_ZIP_URLS: list[str] = [
    "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-2010-04-to-2015-12.zip",
    "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-2016-01-to-2020-12.zip",
]

# ── URL construction ─────────────────────────────────────────────────────────


def _build_csv_url(year: int, month: int) -> str:
    """Build the USDA download URL for a given year/month."""
    return WASDE_CSV_URL_TEMPLATE.format(year=year, month=month)


# ── Manifest helpers ─────────────────────────────────────────────────────────


def _load_manifest(manifest_path: Path) -> dict:
    """Load the ingestion manifest (or empty dict if missing)."""
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest_path: Path, data: dict) -> None:
    """Write the ingestion manifest atomically."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )


# ── HTTP helpers ─────────────────────────────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def _http_get(url: str, *, timeout: int = 60) -> httpx.Response:
    """GET with retry.  Raises on non-2xx (except 404 handled by caller)."""
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp


def _check_availability(url: str) -> bool:
    """Return True if the URL responds with 200 (HEAD request)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            resp = client.head(url)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


def _download_csv(url: str) -> pd.DataFrame | None:
    """Download a WASDE CSV.  Returns None on 404 / unavailable."""
    try:
        resp = _http_get(url)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.info("CSV not available (404): %s", url)
            return None
        raise
    except httpx.HTTPError as exc:
        logger.warning("HTTP error downloading %s: %s", url, exc)
        return None

    df = pd.read_csv(io.StringIO(resp.text), dtype=str)
    # Normalise column names (strip whitespace from headers)
    df.columns = [c.strip() for c in df.columns]
    return df


# ── Schema validation ────────────────────────────────────────────────────────


def _validate_columns(df: pd.DataFrame, url: str) -> bool:
    """Check that the DataFrame has the expected 16 WASDE columns."""
    missing = set(WASDE_COLUMNS) - set(df.columns)
    if missing:
        logger.error("CSV from %s missing columns: %s", url, missing)
        return False
    return True


# ── Core processing ──────────────────────────────────────────────────────────


def _process_csv(df: pd.DataFrame, url: str) -> pd.DataFrame:
    """Add metadata columns and keep only the expected schema columns."""
    df["_source_url"] = url
    df["_ingested_at"] = datetime.now(UTC).isoformat()
    return df


def _save_parquet(
    df: pd.DataFrame,
    year: int,
    month: int,
    output_dir: Path,
) -> Path:
    """Write a single month's data to a Bronze Parquet file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"wasde_{year}_{month:02d}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Bronze WASDE saved: %s (%d rows)", path, len(df))
    return path


def _update_manifest(
    manifest: dict,
    manifest_path: Path,
    key: str,
    df: pd.DataFrame,
) -> None:
    """Record a successfully ingested month in the manifest."""
    wasde_number = None
    if "WasdeNumber" in df.columns and len(df) > 0:
        wasde_number = int(df["WasdeNumber"].iloc[0])

    manifest[key] = {
        "wasde_number": wasde_number,
        "rows": len(df),
        "ingested_at": datetime.now(UTC).isoformat(),
    }
    _save_manifest(manifest_path, manifest)


# ── Public API ───────────────────────────────────────────────────────────────


def backfill_wasde(
    start_year: int = 2010,
    output_dir: Path | None = None,
) -> list[Path]:
    """One-time backfill: download all historical WASDE CSVs from *start_year* to now.

    Steps:
        1. Download + extract ZIPs for 2010-2015 and 2016-2020.
        2. Download individual monthly CSVs for 2021 to current month.
        3. Skip months already recorded in the manifest.

    Args:
        start_year: First year to backfill from (default 2010).
        output_dir: Override for Bronze output directory.

    Returns:
        List of newly created Bronze Parquet paths.
    """
    if output_dir is None:
        output_dir = default_settings.bronze_dir / "wasde"

    manifest_path = output_dir / "_manifest.json"
    manifest = _load_manifest(manifest_path)
    new_paths: list[Path] = []

    # ── Step 1: ZIP archives (2010-2020) ─────────────────────────────────
    if start_year <= 2020:
        for zip_url in WASDE_ZIP_URLS:
            new_paths.extend(
                _ingest_zip(zip_url, output_dir, manifest, manifest_path, start_year)
            )

    # ── Step 2: Individual CSVs (2021 to current) ───────────────────────
    today = date.today()
    csv_start_year = max(start_year, 2021)

    for year in range(csv_start_year, today.year + 1):
        end_month = today.month if year == today.year else 12
        for month in range(1, end_month + 1):
            key = f"{year}-{month:02d}"
            if key in manifest:
                logger.debug("Skipping %s (already ingested)", key)
                continue

            url = _build_csv_url(year, month)
            df = _download_csv(url)
            if df is None:
                continue

            if not _validate_columns(df, url):
                continue

            df = _process_csv(df, url)
            path = _save_parquet(df, year, month, output_dir)
            _update_manifest(manifest, manifest_path, key, df)
            new_paths.append(path)

    logger.info("Backfill complete: %d new files ingested", len(new_paths))
    return new_paths


def _ingest_zip(
    zip_url: str,
    output_dir: Path,
    manifest: dict,
    manifest_path: Path,
    start_year: int,
) -> list[Path]:
    """Download a ZIP archive and extract each CSV inside into its own Parquet."""
    new_paths: list[Path] = []

    logger.info("Downloading ZIP: %s", zip_url)
    try:
        resp = _http_get(zip_url, timeout=300)
    except httpx.HTTPError as exc:
        logger.error("Failed to download ZIP %s: %s", zip_url, exc)
        return new_paths

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith(".csv"):
                continue

            # Parse year/month from filename like oce-wasde-report-data-2010-04.csv
            match = re.search(r"(\d{4})-(\d{2})\.csv$", name, re.IGNORECASE)
            if not match:
                logger.debug("Skipping ZIP entry (no date match): %s", name)
                continue

            year, month = int(match.group(1)), int(match.group(2))
            if year < start_year:
                continue

            key = f"{year}-{month:02d}"
            if key in manifest:
                logger.debug("Skipping %s from ZIP (already ingested)", key)
                continue

            csv_bytes = zf.read(name)
            df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
            df.columns = [c.strip() for c in df.columns]

            source_url = f"{zip_url}!{name}"
            if not _validate_columns(df, source_url):
                continue

            df = _process_csv(df, source_url)
            path = _save_parquet(df, year, month, output_dir)
            _update_manifest(manifest, manifest_path, key, df)
            new_paths.append(path)

    return new_paths


def extract_wasde_latest(
    output_dir: Path | None = None,
) -> Path | None:
    """Monthly incremental: check if current month's CSV is available.

    Checks both the current month and the next month (in case the
    script runs after the report was published).

    Args:
        output_dir: Override for Bronze output directory.

    Returns:
        Path to the new Bronze Parquet, or None if nothing new.
    """
    if output_dir is None:
        output_dir = default_settings.bronze_dir / "wasde"

    manifest_path = output_dir / "_manifest.json"
    manifest = _load_manifest(manifest_path)

    today = date.today()
    candidates = [
        (today.year, today.month),
    ]
    # Also check next month
    if today.month == 12:
        candidates.append((today.year + 1, 1))
    else:
        candidates.append((today.year, today.month + 1))

    for year, month in candidates:
        key = f"{year}-{month:02d}"
        if key in manifest:
            logger.debug("Month %s already ingested — skipping", key)
            continue

        url = _build_csv_url(year, month)
        if not _check_availability(url):
            logger.info("WASDE CSV not yet available for %s", key)
            continue

        df = _download_csv(url)
        if df is None:
            continue

        if not _validate_columns(df, url):
            continue

        df = _process_csv(df, url)
        path = _save_parquet(df, year, month, output_dir)
        _update_manifest(manifest, manifest_path, key, df)
        logger.info("New WASDE report ingested: %s", key)
        return path

    logger.info("No new WASDE CSV available")
    return None
