import pandas as pd

from usda_reports.reports.wasde.xml_layout import XmlLayout, learn


def _xml(rows):
    cols = [
        "xtitle",
        "matrix",
        "xcom",
        "xreg",
        "xattr",
        "market_year",
        "proj_est_flag",
        "period",
        "subtitle",
        "page_title",
        "value",
    ]
    return pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows])


def _csv(rows):
    cols = [
        "report_title",
        "commodity",
        "region",
        "attribute",
        "market_year",
        "period",
        "value",
        "reliability_stat",
        "unit",
        "report_month",
    ]
    return pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows])


def _pair():
    xml = _xml(
        [
            (
                "World Corn",
                "matrix1",
                "",
                "World",
                "Production",
                "2024/25",
                "",
                "annual",
                "MMT",
                "",
                1200.5,
            ),
            (
                "World Corn",
                "matrix1",
                "",
                "World",
                "Ending Stocks",
                "2024/25",
                "",
                "annual",
                "MMT",
                "",
                310.25,
            ),
            (
                "World Corn",
                "matrix1",
                "",
                "Brazil",
                "Production",
                "2024/25",
                "",
                "annual",
                "MMT",
                "",
                127.0,
            ),
        ]
    )
    csv = _csv(
        [
            (
                "World Corn Supply and Use",
                "Corn",
                "World",
                "Production",
                "2024/25",
                "annual",
                1200.5,
                "",
                "Million Metric Tons",
                "2024-05",
            ),
            (
                "World Corn Supply and Use",
                "Corn",
                "World",
                "Ending Stocks",
                "2024/25",
                "annual",
                310.25,
                "",
                "Million Metric Tons",
                "2024-05",
            ),
            (
                "World Corn Supply and Use",
                "Corn",
                "Brazil",
                "Production",
                "2024/25",
                "annual",
                127.0,
                "",
                "Million Metric Tons",
                "2024-05",
            ),
        ]
    )
    return xml, csv


def _layout():
    xml, csv = _pair()
    tables = learn([(xml, csv)] * 3)  # >= 3 votes per position
    units = csv[["report_title", "commodity", "attribute", "unit"]]
    return XmlLayout(
        tables["positions"], tables["position_attributes"], tables["attributes"], units
    )


def test_learn_maps_positions():
    layout = _layout()
    pos = layout.positions.set_index(["xtitle", "matrix", "xcom", "xreg"])
    assert pos.loc[("World Corn", "matrix1", "", "World"), "commodity"] == "Corn"


def test_apply_exact_and_group_fallback_for_unseen_region():
    layout = _layout()
    old = _xml(
        [
            (
                "World Corn",
                "matrix1",
                "",
                "FSU-12",
                "Production",
                "2010/11",
                "Proj.",
                "annual",
                "MMT",
                "",
                50.0,
            )
        ]
    )
    out = layout.apply(old)
    assert out.iloc[0].to_dict() | {} == {
        "report_title": "World Corn Supply and Use",
        "commodity": "Corn",
        "region": "FSU-12",  # region kept from the XML
        "attribute": "Production",
        "market_year": "2010/11",
        "proj_est_flag": "Proj.",
        "period": "annual",
        "value": 50.0,
        "unit": "Million Metric Tons",
    }
    assert layout.stats["group3"] == 1


def test_apply_drops_unknown_tables():
    layout = _layout()
    out = layout.apply(
        _xml([("Unknown table", "matrix9", "", "", "X", "2024/25", "", "annual", "", "", 1.0)])
    )
    assert out.empty
    assert layout.stats["unmapped"] == 1


def test_aliases_are_applied():
    layout = _layout()
    layout.title_aliases = {"Old World Corn": "World Corn"}
    out = layout.apply(
        _xml(
            [
                (
                    "Old World Corn",
                    "matrix1",
                    "",
                    "World",
                    "Production",
                    "2012/13",
                    "",
                    "annual",
                    "",
                    "",
                    1.0,
                )
            ]
        )
    )
    assert out.report_title.iat[0] == "World Corn Supply and Use"
