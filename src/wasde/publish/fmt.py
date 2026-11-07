"""Human formatting of WASDE quantities, used in headline sentences."""

from __future__ import annotations

_SHORT = {
    "mmt": "MMT",
    "m_bales": "mil. bales",
    "m_bu": "mil. bu",
    "m_acres": "mil. acres",
    "bu_per_acre": "bu/acre",
    "lb_per_acre": "lb/acre",
    "usd_per_bu": "$/bu",
    "usd_per_cwt": "$/cwt",
    "usd_per_short_ton": "$/short ton",
    "cents_per_lb": "¢/lb",
    "m_lbs": "mil. lbs",
    "k_short_tons": "thou. short tons",
    "pct": "%",
}


def unit_short(unit_id: str | None) -> str:
    return _SHORT.get(unit_id or "", unit_id or "")


def _decimals(unit_id: str | None, value: float) -> int:
    if unit_id in {"bu_per_acre", "m_acres"}:
        return 1
    if unit_id in {"usd_per_bu", "usd_per_cwt", "cents_per_lb"}:
        return 2
    if unit_id in {"mmt", "m_bales"}:
        return 2 if abs(value) < 10 else 1
    return 0


def quantity(value: float, unit_id: str | None) -> str:
    """1925 m_bu -> '1.93 bil. bu'; 280.44 mmt -> '280.4 MMT'; 181.2 bu/acre -> '181.2 bu/acre'."""
    if unit_id == "m_bu" and abs(value) >= 1000:
        return f"{value / 1000:,.2f} bil. bu"
    if unit_id == "m_lbs" and abs(value) >= 1000:
        return f"{value / 1000:,.2f} bil. lbs"
    if unit_id == "usd_per_bu":
        return f"${value:,.2f}/bu"
    d = _decimals(unit_id, value)
    return f"{value:,.{d}f} {unit_short(unit_id)}".strip()


def delta(value: float, unit_id: str | None) -> str:
    """Signed change: '+75 mil. bu', '−2.8 MMT'."""
    sign = "+" if value > 0 else "−" if value < 0 else "±"
    if unit_id == "usd_per_bu":
        return f"{sign}${abs(value):,.2f}/bu"
    d = max(_decimals(unit_id, value), 1 if unit_id in {"mmt", "m_bales"} else 0)
    return f"{sign}{abs(value):,.{d}f} {unit_short(unit_id)}".strip()


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return ""
    sign = "+" if value > 0 else "−" if value < 0 else "±"
    return f"{sign}{abs(value) * 100:.{digits}f}%"
