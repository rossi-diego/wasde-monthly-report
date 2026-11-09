import pytest

from usda_reports.reports.wasde.text import (
    clean_label,
    flag_from_text,
    label_key,
    market_year_label,
    parse_number,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("World  3/", "World"),
        ("Total Use 2/", "Total Use"),
        ("Beginning\r\nStocks", "Beginning Stocks"),
        ("World Wheat Supply and Use  1/  (Cont'd.)", "World Wheat Supply and Use"),
        ("Million  Pounds /4", "Million Pounds"),
        ("$/bu", "$/bu"),
        ("EU-27+UK", "EU-27+UK"),
        (None, ""),
        (float("nan"), ""),
    ],
)
def test_clean_label(raw, expected):
    assert clean_label(raw) == expected


def test_label_key_ignores_case_space_punctuation():
    assert label_key("Ending Stocks, Total") == label_key("ending stocks total")
    assert label_key("Total  Domestic") == label_key("Total Domestic")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2023/24 (Est.) ", "2023/24"),
        ("2024/25 Proj.", "2024/25"),
        ("2010/011 Proj.", "2010/11"),
        ("2024 Proj.", "2024"),
        ("", ""),
    ],
)
def test_market_year_label(raw, expected):
    assert market_year_label(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2024/25 Proj.", "Proj."), ("2023/24 (Est.)", "Est."), ("2022/23", "")],
)
def test_flag_from_text(raw, expected):
    assert flag_from_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,234.98", 1234.98),
        ("101.3 *", 101.3),
        (".00", 0.0),
        ("NA", None),
        ("", None),
        ("abc", None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_price_range_becomes_midpoint():
    assert parse_number("7.50 - 8.90") == 8.2
    assert parse_number("6.20-6.30") == 6.25
