"""Runtime settings. Everything configurable lives here and is overridable by env vars."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    """Pipeline settings (env prefix ``WASDE_``)."""

    model_config = SettingsConfigDict(env_prefix="WASDE_", env_file=".env", extra="ignore")

    data_dir: Path = PROJECT_ROOT / "data"
    config_dir: Path = PROJECT_ROOT / "config"
    web_data_dir: Path = PROJECT_ROOT / "web" / "public" / "data"
    dbt_dir: Path = PROJECT_ROOT / "dbt"

    log_level: str = "INFO"
    log_json: bool = False

    # USDA's CDN (Akamai) rejects non-browser user agents with HTTP 403.
    user_agent: str = BROWSER_USER_AGENT
    http_timeout_s: float = 90.0

    usda_csv_url: str = "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-{year}-{month:02d}.csv"
    usda_calendar_url: str = (
        "https://www.usda.gov/about-usda/general-information/staff-offices/"
        "office-chief-economist/commodity-markets/wasde-report"
    )
    esmis_api_url: str = "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/wasde"

    # Earliest report with machine-readable (XML) tables.
    history_start: str = "2010-07"
    # Minimum rows per report (May/June reports carry ~3,980; normal ~4,000-5,000).
    min_rows_per_report: int = 3500

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"

    @property
    def publish_dir(self) -> Path:
        return self.data_dir / "publish"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.json"

    @property
    def duckdb_path(self) -> Path:
        return self.gold_dir / "wasde.duckdb"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
