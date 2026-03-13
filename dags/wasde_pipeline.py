# dags/wasde_pipeline.py
"""WASDE Medallion Pipeline — Airflow DAG.

Schedule: 12th of each month at 14:00 UTC (day after typical WASDE release).

Architecture:
    Bronze (parallel) ──► Silver (parallel) ──► Gold (single)
    extract_psd ──► transform_psd ──┐
    extract_nopa ──► transform_nopa ──┤──► build_gold
    extract_exports ──► transform_exports ──┘

Key patterns:
    - @dag / @task decorators (TaskFlow API — modern Airflow style)
    - Business logic imported inside @task (avoids DAG parse-time import errors)
    - Tasks return string paths via XCom (serialisable primitives only)
    - catchup=False (no auto-backfill of missed runs)
    - retries=2 per task with 10 min delay
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pendulum
from airflow.decorators import dag, task


@dag(
    dag_id="wasde_pipeline",
    schedule="0 14 12 * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
    },
    tags=["wasde", "usda", "medallion"],
    doc_md="""
    ## WASDE Medallion Pipeline

    Runs on the 12th of each month, fetching the latest WASDE, NOPA, and
    USDA export data, validating it through Bronze → Silver → Gold layers,
    and materialising the Gold DuckDB tables for the FastAPI app.
    """,
)
def wasde_pipeline() -> None:

    # ── Bronze: parallel extraction ──────────────────────────────────────

    @task()
    def extract_psd_task() -> str:
        from wasde.config import settings
        from wasde.pipelines.bronze.psd import extract_psd

        api_key = os.environ["USDA_PSD_KEY"]
        path = extract_psd(api_key=api_key, run_date=date.today(), output_dir=settings.bronze_dir / "psd")
        return str(path)

    @task()
    def extract_nopa_task() -> str:
        from wasde.config import settings
        from wasde.pipelines.bronze.nopa import extract_nopa

        path = extract_nopa(run_date=date.today(), output_dir=settings.bronze_dir / "nopa")
        return str(path)

    @task()
    def extract_exports_task() -> str:
        from wasde.config import settings
        from wasde.pipelines.bronze.exports import extract_exports

        path = extract_exports(run_date=date.today(), output_dir=settings.bronze_dir / "exports")
        return str(path)

    # ── Silver: validate + clean (each depends on its bronze task) ────────

    @task()
    def transform_psd_task(bronze_path: str) -> str:
        from wasde.config import settings
        from wasde.pipelines.silver.psd import transform_psd

        silver_path = settings.silver_dir / "psd.parquet"
        transform_psd(Path(bronze_path), silver_path)
        return str(silver_path)

    @task()
    def transform_nopa_task(bronze_path: str) -> str:
        from wasde.config import settings
        from wasde.pipelines.silver.nopa import transform_nopa

        silver_path = settings.silver_dir / "nopa.parquet"
        transform_nopa(Path(bronze_path), silver_path)
        return str(silver_path)

    @task()
    def transform_exports_task(bronze_path: str) -> str:
        from wasde.config import settings
        from wasde.pipelines.silver.exports import transform_exports

        silver_path = settings.silver_dir / "exports.parquet"
        transform_exports(Path(bronze_path), silver_path)
        return str(silver_path)

    # ── Gold: aggregate + materialise DuckDB (fan-in) ─────────────────────

    @task()
    def build_gold_task(
        _silver_psd: str,
        _silver_nopa: str,
        _silver_exports: str,
    ) -> None:
        from wasde.pipelines.gold.metrics import build_gold

        build_gold()

    # ── Wire up the dependency graph ─────────────────────────────────────

    b_psd = extract_psd_task()
    b_nopa = extract_nopa_task()
    b_exp = extract_exports_task()

    s_psd = transform_psd_task(b_psd)
    s_nopa = transform_nopa_task(b_nopa)
    s_exp = transform_exports_task(b_exp)

    build_gold_task(s_psd, s_nopa, s_exp)


wasde_pipeline()
