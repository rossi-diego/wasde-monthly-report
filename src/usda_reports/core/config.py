"""Runtime settings. Everything configurable lives here and is overridable by env vars.

Env prefix is ``USDA_``. The pre-2.1 prefix ``WASDE_`` is still honoured for one release:
any ``WASDE_X`` without a matching ``USDA_X`` is copied over and a deprecation line is logged.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_PREFIX = "USDA_"
LEGACY_ENV_PREFIX = "WASDE_"

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    """Pipeline settings (env prefix ``USDA_``; ``WASDE_`` accepted as a deprecated fallback)."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_file=".env", extra="ignore", populate_by_name=True
    )

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
    # Minimum rows per WASDE report (May/June reports carry ~3,980; normal ~4,000-5,000).
    # Overrides the value in config/contracts/wasde.yaml when set.
    min_rows_per_report: int | None = None

    # API keys (read without the USDA_ prefix). FAS Export Sales reuses the PSD key.
    fas_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("FAS_API_KEY", "USDA_PSD_KEY")
    )
    nass_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("NASS_API_KEY")
    )

    # Optional separate bronze location (default: <data_dir>/bronze). Lets a scratch build
    # (e.g. the parity test) read an existing bronze store without copying 300 MB.
    bronze_path: Path | None = None

    @property
    def bronze_dir(self) -> Path:
        return self.bronze_path or self.data_dir / "bronze"

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
        return self.gold_dir / "usda_reports.duckdb"

    @property
    def calendars_dir(self) -> Path:
        return self.config_dir / "calendars"

    def report_config_dir(self, report_id: str) -> Path:
        """Per-report config folder, e.g. ``config/reports/wasde``."""
        return self.config_dir / "reports" / report_id


def _dotenv_pairs(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader for the legacy fallback (comments and blanks skipped)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def apply_legacy_env(env: dict[str, str] | None = None, dotenv: Path | None = None) -> list[str]:
    """Copy ``WASDE_X`` to ``USDA_X`` when only the old name is set. Returns the old names used.

    ``env`` defaults to ``os.environ`` (mutated in place, so subprocesses such as dbt see the
    new names too). Values from ``.env`` are considered as well.
    """
    target = os.environ if env is None else env
    sources = {**_dotenv_pairs(dotenv or Path(".env")), **target}
    used = []
    for key, value in sorted(sources.items()):
        if not key.startswith(LEGACY_ENV_PREFIX):
            continue
        new = ENV_PREFIX + key[len(LEGACY_ENV_PREFIX) :]
        if new not in target and new not in sources:
            target[new] = value
            used.append(key)
    return used


# Old variable names that were mapped by ``get_settings`` (logged by the CLI once logging is up).
LEGACY_ENV_USED: list[str] = []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    LEGACY_ENV_USED[:] = apply_legacy_env()
    return Settings()
