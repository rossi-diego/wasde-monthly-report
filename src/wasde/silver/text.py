"""Label normalization helpers shared by both parsers."""

from __future__ import annotations

import math
import re

_WS = re.compile(r"\s+")
_FOOTNOTE = re.compile(r"\s*\b\d{1,2}/(?!\d)\s*")  # "World 3/", "Total Use 2/"
_TRAILING_FN = re.compile(r"\s*/\d{1,2}\b")  # "Pounds /4"
_CONTD = re.compile(r"\(\s*Cont'?d\.?\s*\)", re.IGNORECASE)
_MY = re.compile(r"(\d{4})\s*(?:/\s*(\d{2,3}))?")


def squash(s: object) -> str:
    """Collapse whitespace (incl. CR/LF) and strip. ``None``/NaN -> ''."""
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ""
    return _WS.sub(" ", str(s)).strip()


def clean_label(s: object) -> str:
    """Strip footnote markers, "(Cont'd.)", trailing asterisks; collapse whitespace."""
    t = squash(s)
    t = _CONTD.sub("", t)
    t = _FOOTNOTE.sub(" ", t)
    t = _TRAILING_FN.sub("", t)
    return squash(t).strip(" *")


def label_key(s: object) -> str:
    """Case/space/punctuation-insensitive key, for matching label variants."""
    return re.sub(r"[^a-z0-9]", "", clean_label(s).lower())


def market_year_label(s: object) -> str:
    """'2023/24 (Est.)' -> '2023/24'; '2010/011 Proj.' -> '2010/11'; '2024 Proj.' -> '2024'."""
    m = _MY.search(squash(s))
    if not m:
        return ""
    start, end = m.group(1), m.group(2)
    return f"{start}/{end[-2:]}" if end else start


def flag_from_text(s: object) -> str:
    t = squash(s).lower()
    if "proj" in t:
        return "Proj."
    if "est" in t:
        return "Est."
    return ""


def parse_number(s: object) -> float | None:
    """'1,234.98' -> 1234.98; '101.3 *' -> 101.3; 'NA'/'' -> None."""
    t = squash(s).replace(",", "").replace("*", "").strip()
    if not t or t.upper() in {"NA", "N/A", "-", "--"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None
