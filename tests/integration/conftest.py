"""Shared mini build: silver → dbt gold → publish on two fixture reports (built once).

Two reports are built from the trimmed 2024-05 CSV fixture: an "April" copy and the real
May file, with U.S. corn ending stocks moved so that drivers and highlights have a revision
to explain. Only U.S./World corn exist, which also checks that publishing degrades
gracefully when a focus commodity has no data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from usda_reports.core.config import PROJECT_ROOT, Settings
from usda_reports.core.manifest import Manifest, ReleaseEntry, release_ts_utc


@pytest.fixture(scope="session")
def built(tmp_path_factory, request) -> Settings:
    pytest.importorskip("dbt")
    from usda_reports.gold import run_dbt
    from usda_reports.publish.run import publish_all
    from usda_reports.reports.wasde.harmonize import SILVER_COLUMNS, Vocabulary, harmonize
    from usda_reports.reports.wasde.parse_csv import parse_csv
    from usda_reports.silver.envelope import add_envelope

    root = tmp_path_factory.mktemp("wasde")
    fixtures = Path(request.config.rootpath) / "tests" / "fixtures"
    settings = Settings(
        data_dir=root / "data", web_data_dir=root / "web", config_dir=PROJECT_ROOT / "config"
    )

    may = parse_csv(fixtures / "wasde_2024-05.csv", "2024-05")
    april = may.copy()
    april["report_month"] = "2024-04"
    april["wasde_number"] = 647
    corn_es = (
        (april.report_title.str.startswith("U.S. Feed"))
        & (april.commodity == "Corn")
        & (april.attribute == "Ending Stocks")
    )
    corn_prod = (
        (april.report_title.str.startswith("U.S. Feed"))
        & (april.commodity == "Corn")
        & (april.attribute == "Production")
    )
    april.loc[corn_es, "value"] += 100  # May "cut" ending stocks by 100 ...
    april.loc[corn_prod, "value"] += 100  # ... explained entirely by production
    raw = pd.concat([april, may], ignore_index=True)
    silver, _ = harmonize(
        raw, Vocabulary.load(settings.report_config_dir("wasde") / "mappings.yaml")
    )
    manifest = Manifest()
    for month, day in (("2024-04", "2024-04-11"), ("2024-05", "2024-05-10")):
        manifest.releases("wasde")[month] = ReleaseEntry(
            source="usda_csv",
            file=f"usda_csv/{month}.csv",
            sha256="0" * 64,
            release_date=day,
            release_ts_utc=release_ts_utc(day),
        )
    silver = add_envelope(
        silver[SILVER_COLUMNS], "wasde", "report_month", manifest.releases("wasde")
    )
    settings.silver_dir.mkdir(parents=True)
    silver.to_parquet(settings.silver_dir / "wasde.parquet", index=False)

    assert run_dbt(settings, command="run") == 0
    publish_all(settings, manifest, tag="data-2024-05")
    manifest.save(settings.manifest_path)
    return settings
