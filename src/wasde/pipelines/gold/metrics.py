# src/wasde/pipelines/gold/metrics.py
"""Gold layer — materialise DuckDB tables from Silver Parquet.

Three tables are created/replaced on every run:
  gold_supply_demand  — PSD with stock-to-use ratio + revision tracking
  gold_nopa_crush     — NOPA monthly crush + crush margin
  gold_export_pace    — ESR weekly pace vs. USDA annual target
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from wasde.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


def build_gold(cfg: Settings | None = None) -> None:
    """Read Silver Parquet files and materialise Gold DuckDB tables.

    Args:
        cfg: Settings instance (defaults to module-level settings).
    """
    if cfg is None:
        cfg = default_settings

    silver_psd = cfg.silver_dir / "psd.parquet"
    silver_nopa = cfg.silver_dir / "nopa.parquet"
    silver_exports = cfg.silver_dir / "exports.parquet"

    cfg.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(cfg.duckdb_path))

    try:
        _build_supply_demand(con, silver_psd)
        _build_nopa_crush(con, silver_nopa)
        _build_export_pace(con, silver_exports, silver_psd)
        logger.info("Gold layer materialised at %s", cfg.duckdb_path)
    finally:
        con.close()


def _build_supply_demand(con: duckdb.DuckDBPyConnection, silver_path: Path) -> None:
    if not silver_path.exists():
        logger.warning("Silver PSD not found: %s — skipping gold_supply_demand", silver_path)
        return

    con.execute(f"""
        CREATE OR REPLACE TABLE gold_supply_demand AS
        WITH pivoted AS (
            SELECT
                report_date,
                commodity,
                country,
                marketing_year,
                unit,
                MAX(CASE WHEN attribute = 'Beginning Stocks'  THEN value END) AS beginning_stocks,
                MAX(CASE WHEN attribute = 'Production'        THEN value END) AS production,
                MAX(CASE WHEN attribute = 'Imports'           THEN value END) AS imports,
                MAX(CASE WHEN attribute IN ('Dom. Consumption', 'Domestic Total') THEN value END) AS domestic_total,
                MAX(CASE WHEN attribute = 'Exports'           THEN value END) AS exports,
                MAX(CASE WHEN attribute = 'Ending Stocks'     THEN value END) AS ending_stocks
            FROM read_parquet('{silver_path}')
            GROUP BY report_date, commodity, country, marketing_year, unit
        )
        SELECT
            *,
            CASE
                WHEN domestic_total > 0 AND ending_stocks IS NOT NULL
                THEN ROUND(ending_stocks / domestic_total * 100, 2)
                ELSE NULL
            END AS stock_to_use_pct,
            ending_stocks - LAG(ending_stocks) OVER (
                PARTITION BY commodity, country, marketing_year
                ORDER BY report_date
            ) AS revision_ending_stocks
        FROM pivoted
    """)
    logger.info("gold_supply_demand built")


def _build_nopa_crush(con: duckdb.DuckDBPyConnection, silver_path: Path) -> None:
    if not silver_path.exists():
        logger.warning("Silver NOPA not found: %s — skipping gold_nopa_crush", silver_path)
        return

    # Crush margin = (meal_price * meal_yield) + (oil_price * oil_yield) - soy_price
    # Simplified version without live price data — margin set to NULL until prices are added
    con.execute(f"""
        CREATE OR REPLACE TABLE gold_nopa_crush AS
        SELECT
            report_date,
            crush_million_bu,
            oil_stocks_million_lbs,
            SUM(crush_million_bu) OVER (
                ORDER BY report_date
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            ) AS rolling_12m_crush,
            NULL::DOUBLE AS crush_margin_usd_per_bu
        FROM read_parquet('{silver_path}')
        ORDER BY report_date
    """)
    logger.info("gold_nopa_crush built")


def _build_export_pace(
    con: duckdb.DuckDBPyConnection,
    silver_exports: Path,
    silver_psd: Path,
) -> None:
    if not silver_exports.exists():
        logger.warning("Silver exports not found — skipping gold_export_pace")
        return

    # Get latest cumulative exports per commodity
    exports_sql = f"""
        SELECT
            commodity,
            MAX(week_ending) AS as_of_date,
            SUM(net_sales_mt) AS cumulative_exports_mt
        FROM read_parquet('{silver_exports}')
        GROUP BY commodity
    """

    if silver_psd.exists():
        # Join with PSD exports target from the latest report
        con.execute(f"""
            CREATE OR REPLACE TABLE gold_export_pace AS
            WITH esr AS ({exports_sql}),
            psd_target AS (
                SELECT
                    commodity,
                    MAX(marketing_year) AS marketing_year,
                    MAX(value) FILTER (WHERE attribute = 'Exports') AS usda_target_mt
                FROM read_parquet('{silver_psd}')
                WHERE report_date = (SELECT MAX(report_date) FROM read_parquet('{silver_psd}'))
                GROUP BY commodity
            )
            SELECT
                esr.commodity,
                psd_target.marketing_year,
                esr.cumulative_exports_mt,
                psd_target.usda_target_mt,
                CASE
                    WHEN psd_target.usda_target_mt > 0
                    THEN ROUND(esr.cumulative_exports_mt / psd_target.usda_target_mt * 100, 1)
                    ELSE NULL
                END AS pace_pct,
                esr.as_of_date
            FROM esr
            LEFT JOIN psd_target USING (commodity)
        """)
    else:
        con.execute(f"""
            CREATE OR REPLACE TABLE gold_export_pace AS
            SELECT
                commodity,
                NULL::INTEGER AS marketing_year,
                SUM(net_sales_mt) AS cumulative_exports_mt,
                NULL::DOUBLE AS usda_target_mt,
                NULL::DOUBLE AS pace_pct,
                MAX(week_ending) AS as_of_date
            FROM read_parquet('{silver_exports}')
            GROUP BY commodity
        """)

    logger.info("gold_export_pace built")
