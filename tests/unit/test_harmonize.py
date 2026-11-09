import pandas as pd
import pytest

from usda_reports.reports.wasde.harmonize import (
    SILVER_COLUMNS,
    RepeatedKeyError,
    Vocabulary,
    harmonize,
)
from usda_reports.reports.wasde.silver import SilverContractError, load_contract, validate


@pytest.fixture
def vocab(config_dir):
    return Vocabulary.load(config_dir / "reports" / "wasde" / "mappings.yaml")


def _raw(rows):
    base = {
        "report_month": "2024-05",
        "wasde_number": 648,
        "release_date": None,
        "reliability_stat": "",
        "region": "United States",
        "proj_est_flag": "Proj.",
        "period": "annual",
        "source": "usda_csv",
        "unit": "Million Bushels",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_label_variants_map_to_one_id(vocab):
    raw = _raw(
        [
            {
                "report_title": "U.S. Feed Grain and Corn Supply and Use",
                "commodity": "Corn",
                "attribute": "Ending Stocks",
                "market_year": "2024/25",
                "value": 1.0,
            },
            {
                "report_title": "U.S. Feed Grain and Corn Supply and Use",
                "commodity": "Corn",
                "attribute": "Ending stocks",
                "market_year": "2023/24",
                "value": 2.0,
            },
            {
                "report_title": "World and U.S Supply and Use for Grains",
                "commodity": "Wheat",
                "attribute": "Ending Stocks, Total",
                "market_year": "2023/24",
                "value": 3.0,
            },
        ]
    )
    silver, unmapped = harmonize(raw, vocab)
    assert set(silver.attribute_id) == {"ending_stocks"}
    assert set(silver.table_id) == {"us_feed_grains_corn", "world_us_grains"}
    assert silver.proj_est_flag.eq("proj").all()
    assert silver.my_start.tolist() == [2024, 2023, 2023]
    assert unmapped.empty


def test_reliability_titles_use_patterns(vocab):
    tid, _, known = vocab.table("Reliability of United States August Projections")
    assert (tid, known) == ("reliability_us", True)
    assert vocab.table("Reliability of May Projections")[0] == "reliability_world"


def test_unknown_labels_are_reported_and_slugified(vocab):
    raw = _raw(
        [
            {
                "report_title": "U.S. Wheat Supply and Use",
                "commodity": "Wheat",
                "attribute": "Brand New Line",
                "market_year": "2024/25",
                "value": 1.0,
            }
        ]
    )
    silver, unmapped = harmonize(raw, vocab)
    assert silver.attribute_id.iat[0] == "brand_new_line"
    assert unmapped.to_dict("records") == [{"kind": "attribute", "label": "Brand New Line"}]


def test_repeated_sublines_are_numbered_and_exact_duplicates_dropped(vocab):
    row = {
        "report_title": "U.S. Sugar Supply and Use",
        "commodity": "Sugar",
        "attribute": "Imports - Other",
        "market_year": "2024/25",
    }
    raw = _raw([{**row, "value": 1.0}, {**row, "value": 1.0}, {**row, "value": 5.0}])
    silver, _ = harmonize(raw, vocab)
    assert sorted(silver.attribute_id) == ["imports_other", "imports_other_2"]


def test_unexpected_repeats_fail(vocab):
    row = {
        "report_title": "U.S. Feed Grain and Corn Supply and Use",
        "commodity": "Corn",
        "attribute": "Ending Stocks",
        "market_year": "2024/25",
    }
    with pytest.raises(RepeatedKeyError):
        harmonize(_raw([{**row, "value": 1.0}, {**row, "value": 2.0}]), vocab)


def test_validate_flags_missing_core_series_and_small_reports(vocab, config_dir):
    rows = []
    core_series = load_contract(config_dir).required_per_release.tuples()
    for table, com, region, attr in core_series:
        rows.append(
            {
                "report_month": "2024-05",
                "table_id": table,
                "commodity_id": com,
                "region_id": region,
                "attribute_id": attr,
                "market_year": "2024/25",
                "period": "annual",
                "reliability_stat": "",
                "value": 1.0,
            }
        )
    df = pd.DataFrame(rows).reindex(columns=[*SILVER_COLUMNS])
    df = df.fillna({"period": "annual", "reliability_stat": ""})
    validate(df, min_rows=1)  # complete report passes
    with pytest.raises(SilverContractError, match="missing core series"):
        validate(df.iloc[1:], min_rows=1)
    with pytest.raises(SilverContractError, match="below 100 rows"):
        validate(df, min_rows=100)


def test_eu_labels_form_one_series(vocab):
    base = {
        "report_title": "World Corn Supply and Use",
        "commodity": "Corn",
        "attribute": "Production",
        "market_year": "2012/13",
        "unit": "Million Metric Tons",
    }
    raw = _raw(
        [
            {**base, "region": "EU-27", "value": 1.0},
            {**base, "region": "EU-27+UK", "market_year": "2020/21", "value": 2.0},
            {**base, "region": "European Union", "market_year": "2024/25", "value": 3.0},
        ]
    )
    silver, _ = harmonize(raw, vocab)
    assert set(silver.region_id) == {"european_union"}


def test_units_follow_the_csv_reference_and_overrides(vocab):
    corn = {
        "report_title": "U.S. Feed Grain and Corn Supply and Use",
        "commodity": "Corn",
        "attribute": "Ethanol & by-products",
    }
    cotton = {
        "report_title": "U.S. Cotton Supply and Use",
        "commodity": "Cotton",
        "attribute": "Avg. Farm Price",
    }
    raw = _raw(
        [
            {
                **corn,
                "market_year": "2024/25",
                "value": 5.0,
                "unit": "Million Bushels",
                "source": "usda_csv",
            },
            {
                **corn,
                "market_year": "2010/11",
                "value": 4.0,
                "unit": "Percent",
                "source": "esmis_xml",
            },  # XML fallback unit
            {
                **cotton,
                "market_year": "2024/25",
                "value": 63.0,
                "unit": "Million 480 Pound Bales",
                "source": "usda_csv",
            },
        ]
    )
    silver, _ = harmonize(raw, vocab)
    eth = silver[silver.attribute_id == "ethanol"]
    assert set(eth.unit_id) == {"m_bu"}
    assert silver.loc[silver.attribute_id == "farm_price", "unit_id"].iat[0] == "cents_per_lb"
