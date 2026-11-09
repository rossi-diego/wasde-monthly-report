import pytest

from wasde.publish import fmt
from wasde.publish.focus import Focus
from wasde.publish.highlights import report_context
from wasde.publish.web_json import _clean, cycle_month, month_label


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1925, "m_bu", "1.93 bil. bu"),
        (850, "m_bu", "850 mil. bu"),
        (280.44, "mmt", "280.4 MMT"),
        (6.05, "mmt", "6.05 MMT"),
        (181.2, "bu_per_acre", "181.2 bu/acre"),
        (4.7, "usd_per_bu", "$4.70/bu"),
    ],
)
def test_quantity(value, unit, expected):
    assert fmt.quantity(value, unit) == expected


def test_delta_and_pct():
    assert fmt.delta(75, "m_bu") == "+75 mil. bu"
    assert fmt.delta(-2.8, "mmt") == "−2.80 MMT"
    assert fmt.pct(-0.038) == "−3.8%"


def test_cycle_month_alignment():
    assert cycle_month("2026-05", "2026/27") == 0  # first projection
    assert cycle_month("2026-10", "2026/27") == 5
    assert cycle_month("2027-05", "2026/27") == 12  # becomes an estimate
    assert cycle_month("2026-10", "2026") is None  # calendar-year series


def test_month_label_and_clean():
    assert month_label("2026-10") == "October 2026"
    assert _clean(float("nan")) is None
    assert _clean(3.0) == 3
    assert _clean(1.23456789) == 1.2346


def test_report_context():
    assert "first survey-based" in report_context("2026-08")
    assert report_context("2026-02") is None


def test_focus_config_is_consistent(config_dir):
    focus = Focus.load(config_dir / "focus.yaml")
    assert set(focus.commodities) == {
        "corn",
        "soybeans",
        "soybean_meal",
        "soybean_oil",
        "wheat",
        "cotton",
    }
    assert all(line.label and "," not in line.id for line in focus.balance_lines)
    assert focus.highlights.floor("us", "corn", "ending_stocks") == 50
    assert focus.highlights.floor("world", "wheat", "ending_stocks") == 2.0  # default
    assert focus.highlights.floor("us", "corn", "unknown") is None
