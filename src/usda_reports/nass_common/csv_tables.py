"""NASS ``*_all_tables.csv`` grammar: one CSV line per printed table line.

Column 1 is the table number; column 2 is the row type:

====  =====================================================================================
t     title line (the first is the report's release line, the second the table title)
h     header line (blank spacer lines are h rows too); a run of h rows starts a block
u     unit line, e.g. ``"(tons)"`` per column
d     data line: label, then values (some tables also carry a unit column)
c     comment / continuation line
f     footnote line
====  =====================================================================================

Values use NASS symbols: ``(D)`` withheld to avoid disclosing individual operations,
``(NA)`` not available, ``(X)`` not applicable, ``(Z)`` less than half the unit, ``(S)``
insufficient reports, ``-`` represents zero. Numbers may carry thousands separators. Crop
Progress also prints a bare ``NA`` (not available) and marks revised previous-week values with
a leading asterisk (``"* 61"``, footnote "*  Revised.").

Files are Windows-1252 (en dashes in titles); UTF-8 is tried first.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

ROW_TYPES = frozenset("thudcf")
# Symbol → flag stored next to a null value ("-" is a real zero and keeps flag "zero").
SYMBOLS = {
    "(D)": "D",
    "(NA)": "NA",
    "(X)": "X",
    "(Z)": "Z",
    "(S)": "S",
    "(H)": "H",
    "(L)": "L",
    "NA": "NA",
}
_NUM_RE = re.compile(r"^-?[0-9][0-9,]*(\.[0-9]+)?$")


class NassCsvError(ValueError):
    """The file does not follow the NASS t/h/u/d/c/f grammar."""


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def parse_value(cell: str) -> tuple[float | None, str | None]:
    """(value, flag): ``"6,148,544"`` → (6148544.0, None); ``"(D)"`` → (None, "D");
    ``"-"`` → (0.0, "zero"); ``"* 61"`` → (61.0, "revised"); empty → (None, None)."""
    s = cell.strip()
    if not s:
        return None, None
    if s == "-":
        return 0.0, "zero"
    if s.startswith("*") and _NUM_RE.match(s[1:].strip()):
        return float(s[1:].strip().replace(",", "")), "revised"
    if s.upper() in SYMBOLS:
        return None, SYMBOLS[s.upper()]
    if _NUM_RE.match(s):
        return float(s.replace(",", "")), None
    raise NassCsvError(f"unrecognised NASS value {cell!r}")


@dataclass
class NassBlock:
    """A header run (h rows), its unit rows and the data rows under it."""

    header: list[list[str]] = field(default_factory=list)
    units: list[list[str]] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def header_row(self, first: str) -> list[str] | None:
        """The header line whose first cell equals ``first`` (e.g. 'Item' or 'Region')."""
        return next((h for h in self.header if h and h[0].strip() == first), None)

    def column_labels(self) -> list[str]:
        """One label per column: the non-blank header cells of that column joined top to
        bottom with single spaces (NASS splits headers over lines, e.g. ``"Week ending"`` /
        ``"November 1,"`` / ``"2026"`` → ``"Week ending November 1, 2026"``)."""
        width = max((len(h) for h in self.header), default=0)
        out = []
        for i in range(width):
            parts = [h[i].strip() for h in self.header if i < len(h) and h[i].strip()]
            out.append(re.sub(r"\s+", " ", " ".join(parts)))
        return out


@dataclass
class NassTable:
    number: str
    titles: list[str] = field(default_factory=list)
    blocks: list[NassBlock] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        """The table title (the line after the report's 'Released …' line)."""
        own = [t for t in self.titles if " Released " not in t]
        return own[0] if own else (self.titles[-1] if self.titles else "")


def parse_nass_csv(data: bytes) -> list[NassTable]:
    """Every table of an ``*_all_tables.csv`` file, in file order.

    A table number can appear in several runs (a table continued on the next page); each run
    becomes its own :class:`NassTable` so titles stay attached to their rows."""
    tables: list[NassTable] = []
    cur: NassTable | None = None
    block: NassBlock | None = None
    for lineno, row in enumerate(csv.reader(io.StringIO(decode(data))), start=1):
        if not row or not any(c.strip() for c in row):
            continue
        if len(row) < 2 or row[1] not in ROW_TYPES:
            raise NassCsvError(f"line {lineno}: expected '<table>,<t|h|u|d|c|f>,…', got {row[:3]}")
        number, kind, cells = row[0].strip(), row[1], row[2:]
        if cur is None or number != cur.number or (kind == "t" and cur.blocks):
            cur = NassTable(number=number)
            tables.append(cur)
            block = None
        if kind == "t":
            cur.titles.append(cells[0] if cells else "")
        elif kind == "h":
            if block is None or block.units or block.rows:
                block = NassBlock()
                cur.blocks.append(block)
            block.header.append(cells)
        elif kind == "u":
            if block is None:
                block = NassBlock()
                cur.blocks.append(block)
            block.units.append(cells)
        elif kind == "d":
            if block is None:
                block = NassBlock()
                cur.blocks.append(block)
            block.rows.append(cells)
        else:  # c, f
            text = " ".join(c for c in cells if c).strip()
            if text:
                cur.notes.append(text)
    if not tables:
        raise NassCsvError("no NASS tables found")
    return tables


def normalize_title(s: str) -> str:
    """Dash- and space-insensitive form of a NASS title (en/em dashes become ``-``)."""
    return re.sub(r"\s+", " ", s.replace("–", "-").replace("—", "-")).strip()


def find_tables(tables: list[NassTable], title_prefix: str) -> list[NassTable]:
    """Tables whose title starts with ``title_prefix`` (dash/space-insensitive)."""
    want = normalize_title(title_prefix)
    return [t for t in tables if normalize_title(t.title).startswith(want)]
