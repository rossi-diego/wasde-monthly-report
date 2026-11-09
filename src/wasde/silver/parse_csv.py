"""Parse the official USDA WASDE CSV (2021+) into the raw long schema."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from wasde.silver import RAW_COLUMNS
from wasde.silver.text import squash

EXPECTED = [
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
_PERIOD = {"Annual": "annual", "I": "Q1", "II": "Q2", "III": "Q3", "IV": "Q4"}


class CsvSchemaError(ValueError):
    pass


def parse_csv(source: Path | bytes, report_month: str) -> pd.DataFrame:
    raw = source if isinstance(source, bytes) else source.read_bytes()
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    missing = set(EXPECTED) - set(df.columns)
    if missing:
        raise CsvSchemaError(f"{report_month}: CSV missing columns {sorted(missing)}")

    for col in ["ReportTitle", "Attribute", "Commodity", "Region", "Unit", "MarketYear"]:
        df[col] = df[col].map(squash)

    # ReleaseDate switched from MM/DD/YYYY (2021) to ISO (2025+).
    release = pd.to_datetime(df["ReleaseDate"], format="mixed", errors="coerce").dt.date
    out = pd.DataFrame(
        {
            "report_month": report_month,
            "wasde_number": pd.to_numeric(df["WasdeNumber"], errors="coerce").astype("Int64"),
            "release_date": release,
            "report_title": df["ReportTitle"],
            "attribute": df["Attribute"],
            "reliability_stat": df["ReliabilityProjection"].map(squash),
            "commodity": df["Commodity"],
            "region": df["Region"],
            "market_year": df["MarketYear"],
            "proj_est_flag": df["ProjEstFlag"].map(squash).str.strip("()"),
            "period": df["AnnualQuarterFlag"].map(squash).map(_PERIOD).fillna("annual"),
            "value": pd.to_numeric(df["Value"].str.replace(",", ""), errors="coerce"),
            "unit": df["Unit"],
            "source": "usda_csv",
        }
    )
    return out.dropna(subset=["value"])[RAW_COLUMNS].reset_index(drop=True)
