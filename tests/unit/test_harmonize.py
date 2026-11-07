import pandas as pd
import pytest

from wasde.silver.build import CORE_SERIES, SilverContractError, validate
from wasde.silver.harmonize import SILVER_COLUMNS, Vocabulary, harmonize


@pytest.fixture
def vocab(config_dir):
    return Vocabulary.load(config_dir / "mappings.yaml")


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
        "attribute": "Imports",
        "market_year": "2024/25",
    }
    raw = _raw([{**row, "value": 1.0}, {**row, "value": 1.0}, {**row, "value": 5.0}])
    silver, _ = harmonize(raw, vocab)
    assert sorted(silver.attribute_id) == ["imports", "imports_2"]


def test_validate_flags_missing_core_series_and_small_reports(vocab):
    rows = []
    for table, com, region, attr in CORE_SERIES:
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
