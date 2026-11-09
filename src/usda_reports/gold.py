"""Gold layer: run the dbt-duckdb project (seeds, models + data tests) on top of silver."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from usda_reports.core.calendar import load_calendar
from usda_reports.core.config import Settings
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import release_ts_utc
from usda_reports.core.registry import load_registry

log = get_logger(__name__)


def write_calendar(settings: Settings) -> Path:
    """Flatten every enabled report's calendar into ``silver/calendar.parquet`` (dim_calendar)."""
    rows = []
    for cfg in load_registry(settings.config_dir).enabled():
        for d in load_calendar(settings.calendars_dir / f"{cfg.id}.yaml"):
            rows.append(
                {
                    "report_id": cfg.id,
                    "release_date": d,
                    "release_ts_utc": pd.Timestamp(release_ts_utc(d, cfg.release_time_et)),
                    "cadence": cfg.cadence,
                }
            )
    df = pd.DataFrame(rows, columns=["report_id", "release_date", "release_ts_utc", "cadence"])
    df["release_ts_utc"] = pd.to_datetime(df["release_ts_utc"], utc=True)
    settings.silver_dir.mkdir(parents=True, exist_ok=True)
    out = settings.silver_dir / "calendar.parquet"
    df.to_parquet(out, index=False)
    return out


def write_countries(settings: Settings) -> Path:
    """``config/vocab/countries.yaml`` → ``silver/countries.parquet`` (dim_country)."""
    import yaml

    raw = yaml.safe_load((settings.config_dir / "vocab" / "countries.yaml").read_text("utf-8"))
    rows = [
        {
            "country_id": cid,
            "label": spec["label"],
            "esr_country_code": spec.get("code"),
            "genc_code": spec.get("genc"),
        }
        for cid, spec in raw["items"].items()
    ]
    df = pd.DataFrame(rows, columns=["country_id", "label", "esr_country_code", "genc_code"])
    settings.silver_dir.mkdir(parents=True, exist_ok=True)
    out = settings.silver_dir / "countries.parquet"
    df.to_parquet(out, index=False)
    return out


def dbt_target_dir(settings: Settings) -> Path:
    return settings.gold_dir / "dbt_target"


def run_dbt(
    settings: Settings, command: str = "build", select: str | None = None, fresh: bool = True
) -> int:
    """Invoke dbt in-process. Returns 0 on success.

    ``run`` (used by the fast integration test) seeds first, so models that join seeds work.
    ``fresh=False`` keeps the existing warehouse (e.g. ``test`` on an already built gold);
    ``select`` is passed to ``--select``.
    """
    from dbt.cli.main import dbtRunner

    settings.gold_dir.mkdir(parents=True, exist_ok=True)
    if fresh and settings.duckdb_path.exists():
        settings.duckdb_path.unlink()  # full deterministic rebuild
    os.environ["USDA_DUCKDB_PATH"] = str(settings.duckdb_path)
    write_calendar(settings)
    write_countries(settings)
    silver_dir = settings.silver_dir.resolve().as_posix()
    common = [
        "--project-dir",
        str(settings.dbt_dir),
        "--profiles-dir",
        str(settings.dbt_dir),
        "--vars",
        json.dumps({"silver_dir": silver_dir}),
        # manifest.json (the source of the published data dictionary) lands next to gold.
        "--target-path",
        str(dbt_target_dir(settings).resolve()),
    ]
    if select:
        common += ["--select", select]
    steps = [["seed", *common, "--quiet"]] if command == "run" and fresh else []
    steps.append([command, *common, "--quiet" if command == "build" else "--no-quiet"])
    ok = True
    runner = dbtRunner()
    for args in steps:
        result = runner.invoke(args)
        ok = bool(result.success)
        if not ok:
            if result.exception:
                log.error("gold.dbt_exception", error=str(result.exception))
            break
    _release_connections()
    log.info("gold.dbt", command=command, success=ok, duckdb=str(settings.duckdb_path))
    return 0 if ok else 1


def _release_connections() -> None:
    """dbt-duckdb keeps its DuckDB handle alive in-process; release it so later steps
    (publish, tests) can open the same file."""
    try:
        from dbt.adapters.factory import cleanup_connections, reset_adapters

        cleanup_connections()
        reset_adapters()
    except Exception:  # pragma: no cover - best effort across dbt versions
        log.debug("gold.release_failed")
    import gc

    gc.collect()
