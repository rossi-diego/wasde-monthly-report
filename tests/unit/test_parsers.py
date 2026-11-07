from datetime import date

import pandas as pd
import pytest

from wasde.config import PROJECT_ROOT
from wasde.silver import RAW_COLUMNS
from wasde.silver.parse_csv import CsvSchemaError, parse_csv
from wasde.silver.parse_xml import (
    cells_frame,
    flatten,
    is_current_column,
    parse_xml,
    wasde_number_from,
)
from wasde.silver.xml_layout import XmlLayout


def test_parse_csv_schema_and_values(fixtures):
    df = parse_csv(fixtures / "wasde_2024-05.csv", "2024-05")
    assert list(df.columns) == RAW_COLUMNS
    assert df["report_month"].eq("2024-05").all()
    assert df["release_date"].iloc[0] == date(2024, 5, 10)
    es = df[
        (df.report_title == "U.S. Feed Grain and Corn Supply and Use")
        & (df.commodity == "Corn")
        & (df.attribute == "Ending Stocks")
        & (df.market_year == "2024/25")
    ]
    assert es.value.iat[0] == 2102.0
    assert set(df.proj_est_flag) <= {"Proj.", "Est.", ""}  # parentheses stripped


def test_parse_csv_2021_date_format_and_reliability(fixtures):
    df = parse_csv(fixtures / "wasde_2021-01_sample.csv", "2021-01")
    assert df["release_date"].iloc[0] == date(2021, 1, 12)  # MM/DD/YYYY era
    assert (df.reliability_stat == "average").any()


def test_parse_csv_rejects_missing_columns():
    with pytest.raises(CsvSchemaError):
        parse_csv(b"WasdeNumber,Value\n1,2\n", "2024-01")


@pytest.mark.parametrize(
    ("fm", "month", "expected"),
    [
        ("", "2024-05", True),
        ("May", "2024-05", True),
        ("Apr", "2024-05", False),
        ("April", "2024-05", False),
        ("II", "2024-05", True),
    ],
)
def test_is_current_column(fm, month, expected):
    assert is_current_column(fm, month) is expected


def test_flatten_keeps_only_current_column(fixtures):
    frame = cells_frame(flatten(fixtures / "wasde_2024-05_sr12.xml"), "2024-05")
    assert not frame.empty
    assert wasde_number_from(frame) == 648
    # The XML repeats the projection year for April and May; only May survives.
    corn_area = frame[
        (frame.matrix == "matrix2")
        & (frame.xattr == "Area Planted")
        & (frame.market_year == "2024/25")
    ]
    assert len(corn_area) == 1


def test_namespaced_xml_is_parsed(fixtures):
    """2010-07 and 2015-01 carry an XML namespace on every tag."""
    frame = cells_frame(flatten(fixtures / "wasde_2015-01_sr12_namespaced.xml"), "2015-01")
    assert set(frame.matrix) >= {"matrix1", "matrix2"}


def test_xml_maps_to_csv_vocabulary_and_matches_csv(fixtures):
    layout = XmlLayout.load(PROJECT_ROOT / "config" / "xml_layout")
    xml = parse_xml(fixtures / "wasde_2024-05_sr12.xml", "2024-05", date(2024, 5, 10), layout)
    csv = parse_csv(fixtures / "wasde_2024-05.csv", "2024-05")
    key = ["report_title", "commodity", "region", "attribute", "market_year"]
    us = csv[csv.report_title == "U.S. Feed Grain and Corn Supply and Use"]
    joined = us.merge(xml, on=key, suffixes=("_csv", "_xml"))
    assert len(joined) >= 0.95 * len(us)
    assert (joined.value_csv - joined.value_xml).abs().max() < 1e-9
    assert (joined.unit_csv == joined.unit_xml).all()


def test_world_table_regions_map(fixtures):
    layout = XmlLayout.load(PROJECT_ROOT / "config" / "xml_layout")
    xml = parse_xml(fixtures / "wasde_2024-05_sr22.xml", "2024-05", date(2024, 5, 10), layout)
    world = xml[
        (xml.region == "World") & (xml.attribute == "Production") & (xml.market_year == "2023/24")
    ]
    assert world.report_title.iat[0] == "World Corn Supply and Use"
    assert world.unit.iat[0] == "Million Metric Tons"
    assert isinstance(xml, pd.DataFrame)
