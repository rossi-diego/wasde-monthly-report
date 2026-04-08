"""Seed the DuckDB from the existing wasde_commodities_timeseries.csv.

This bypasses the normal bronze→silver→gold pipeline by building the
gold tables directly from the pre-processed timeseries CSV.
"""

import duckdb
import pandas as pd
from pathlib import Path

CSV_PATH = Path("data/raw_data/wasde_commodities_timeseries.csv")
DB_PATH = Path("data/wasde.duckdb")
SILVER_DIR = Path("data/silver")

df = pd.read_csv(CSV_PATH)
print(f"Input: {len(df)} rows, {df['commodity'].nunique()} commodities")
print(f"Date range: {df['report_date'].min()} to {df['report_date'].max()}")

# Create DuckDB directly from the timeseries (skip silver parquet)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if DB_PATH.exists():
    DB_PATH.unlink()

con = duckdb.connect(str(DB_PATH))

# Build gold_supply_demand (wide format — what the API expects)
df["report_date"] = pd.to_datetime(df["report_date"]).dt.strftime("%Y-%m-%d")

# Rename columns to match API schema
rename = {
    "Beginning Stocks": "beginning_stocks",
    "Production": "production",
    "Imports": "imports",
    "Domestic Total 2": "domestic_total",
    "Exports": "exports",
    "Ending Stocks": "ending_stocks",
}
sd = df.rename(columns=rename)

# Normalize commodity names to match API expectations
commodity_map = {
    "soybean": "Soybeans",
    "soybean meal": "Soybean Meal",
    "soybean oil": "Soybean Oil",
    "wheat": "Wheat",
    "corn": "Corn",
}
sd["commodity"] = sd["commodity"].str.strip().str.lower().map(commodity_map).fillna(sd["commodity"])

# Clean country names (remove footnote markers like "6/")
sd["country"] = sd["country"].str.replace(r"\s*\d+/\s*$", "", regex=True).str.strip()

# Convert marketing_year from "2024/25" to integer 2024
sd["marketing_year"] = sd["marketing_year"].astype(str).str[:4]
sd["marketing_year"] = pd.to_numeric(sd["marketing_year"], errors="coerce").astype("Int64")

# Calculate stock-to-use
sd["stock_to_use_pct"] = sd.apply(
    lambda r: round(r["ending_stocks"] / r["domestic_total"] * 100, 1)
    if pd.notna(r.get("ending_stocks")) and pd.notna(r.get("domestic_total")) and r.get("domestic_total", 0) > 0
    else None,
    axis=1,
)

# Add unit column
sd["unit"] = "1000 MT"

# Revision tracking: month-over-month change in ending stocks
sd = sd.sort_values(["commodity", "country", "marketing_year", "report_date"])
sd["revision_ending_stocks"] = sd.groupby(
    ["commodity", "country", "marketing_year"]
)["ending_stocks"].diff()

# Register as table
con.execute("CREATE TABLE gold_supply_demand AS SELECT * FROM sd")
n = con.execute("SELECT COUNT(*) FROM gold_supply_demand").fetchone()[0]
print(f"gold_supply_demand: {n} rows")

# Build gold_wasde_latest (latest report per commodity/country/MY)
con.execute("""
    CREATE TABLE gold_wasde_latest AS
    SELECT * FROM gold_supply_demand
    WHERE report_date = (SELECT MAX(report_date) FROM gold_supply_demand)
""")
n = con.execute("SELECT COUNT(*) FROM gold_wasde_latest").fetchone()[0]
print(f"gold_wasde_latest: {n} rows")

# Build gold_wasde_revisions (all revision history)
con.execute("""
    CREATE TABLE gold_wasde_revisions AS
    SELECT
        commodity, country, marketing_year, report_date,
        ending_stocks, revision_ending_stocks,
        stock_to_use_pct
    FROM gold_supply_demand
    WHERE ending_stocks IS NOT NULL
    ORDER BY commodity, country, marketing_year, report_date
""")
n = con.execute("SELECT COUNT(*) FROM gold_wasde_revisions").fetchone()[0]
print(f"gold_wasde_revisions: {n} rows")

# Create empty tables for NOPA and exports (API won't crash)
con.execute("""
    CREATE TABLE gold_nopa_crush (
        report_date VARCHAR, crush_million_bu DOUBLE,
        oil_stocks_million_lbs DOUBLE, crush_margin_usd_per_bu DOUBLE,
        rolling_12m_crush DOUBLE
    )
""")
print("gold_nopa_crush: 0 rows (no NOPA data)")

con.execute("""
    CREATE TABLE gold_export_pace (
        commodity VARCHAR, marketing_year INTEGER,
        cumulative_exports_mt DOUBLE, usda_target_mt DOUBLE,
        pace_pct DOUBLE, as_of_date VARCHAR
    )
""")
print("gold_export_pace: 0 rows (no export data)")

con.close()
print(f"\nDuckDB saved: {DB_PATH} ({DB_PATH.stat().st_size:,} bytes)")
print("Done!")
