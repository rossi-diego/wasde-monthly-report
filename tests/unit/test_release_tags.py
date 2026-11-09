"""Release/tag contract helpers and the dataset registry guard (plan §7)."""

from __future__ import annotations

from datetime import date

from usda_reports.publish.catalogue import (
    ALL_DATASETS,
    LEGACY_ALIASES,
    WASDE_DATASETS,
    WASDE_VALUES_COLUMNS,
    WASDE_VALUES_ORDER,
)
from usda_reports.publish.contract import (
    DATA_TAG_RE,
    WEEKLY_TAG_RE,
    is_release_tag,
    release_contract_problems,
    weekly_tag,
)


def test_weekly_tags_are_dated_and_never_reused():
    d = date(2026, 11, 12)
    assert weekly_tag(d, set()) == "weekly-2026-11-12"
    assert weekly_tag(d, {"weekly-2026-11-12"}) == "weekly-2026-11-12.2"
    assert weekly_tag(d, {"weekly-2026-11-12", "weekly-2026-11-12.2"}) == "weekly-2026-11-12.3"
    assert WEEKLY_TAG_RE.match("weekly-2026-11-12.2") and not DATA_TAG_RE.match("weekly-2026-11-12")
    assert is_release_tag("data-2026-11") and is_release_tag("weekly-2026-11-12")
    assert not is_release_tag("bronze-store") and not is_release_tag("v2.0.0")


def test_a_weekly_tag_can_never_satisfy_the_latest_contract():
    meta = {"data_release_tag": "weekly-2026-11-12"}
    problems = release_contract_problems("weekly-2026-11-12", meta, ["wasde_full.parquet"])
    assert any("not a data-YYYY-MM tag" in p for p in problems)


def test_datasets_yaml_keeps_the_legacy_values_dataset_byte_stable():
    values = next(d for d in WASDE_DATASETS if d.stem == "wasde__values__v1")
    cols = ", ".join(c.strip() for c in WASDE_VALUES_COLUMNS.split(","))
    assert values.query == f"select {cols} from fct_wasde order by {WASDE_VALUES_ORDER}"
    assert values.csv_gzip and values.model == "fct_wasde"
    assert LEGACY_ALIASES == {
        "wasde__values__v1.parquet": "wasde_full.parquet",
        "wasde__values__v1.csv.gz": "wasde_full.csv.gz",
    }


def test_catalogue_names_follow_the_convention():
    stems = [d.stem for d in ALL_DATASETS]
    assert len(stems) == len(set(stems))
    assert {
        "export_sales__weekly__v1",
        "export_sales__by_country__v1",
        "cross__export_pace__v1",
    } <= set(stems)
    for d in ALL_DATASETS:
        assert d.stem == f"{d.report_id}__{d.dataset}__v{d.major}"
        assert d.coverage and d.release_column
