# src/wasde/config.py
from __future__ import annotations

import logging
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    usda_psd_key: str = ""
    app_name: str = "WASDE Dashboard"
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    wasde_backfill_start_year: int = 2010

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "wasde.duckdb"

    @property
    def wasde_manifest_path(self) -> Path:
        return self.bronze_dir / "wasde" / "_manifest.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )
