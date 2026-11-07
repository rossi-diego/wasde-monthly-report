"""Gold layer: run the dbt-duckdb project (models + data tests) on top of silver."""

from __future__ import annotations

import json
import os

from wasde.config import Settings
from wasde.logs import get_logger

log = get_logger(__name__)


def run_dbt(settings: Settings, command: str = "build") -> int:
    """Invoke dbt in-process. Returns 0 on success."""
    from dbt.cli.main import dbtRunner

    settings.gold_dir.mkdir(parents=True, exist_ok=True)
    if settings.duckdb_path.exists():
        settings.duckdb_path.unlink()  # full deterministic rebuild
    os.environ["WASDE_DUCKDB_PATH"] = str(settings.duckdb_path)
    silver = (settings.silver_dir / "wasde.parquet").resolve().as_posix()
    args = [
        command,
        "--project-dir",
        str(settings.dbt_dir),
        "--profiles-dir",
        str(settings.dbt_dir),
        "--vars",
        json.dumps({"silver_path": silver}),
        "--quiet" if command == "build" else "--no-quiet",
    ]
    result = dbtRunner().invoke(args)
    ok = bool(result.success)
    log.info("gold.dbt", command=command, success=ok, duckdb=str(settings.duckdb_path))
    if not ok and result.exception:
        log.error("gold.dbt_exception", error=str(result.exception))
    return 0 if ok else 1
