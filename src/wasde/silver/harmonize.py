"""Harmonize raw long rows into canonical ids (table, commodity, region, attribute, unit)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from wasde.silver.text import label_key

SILVER_KEY = [
    "report_month",
    "table_id",
    "commodity_id",
    "region_id",
    "attribute_id",
    "market_year",
    "period",
    "reliability_stat",
]


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "unknown"


@dataclass
class Vocabulary:
    tables: dict[str, tuple[str, str]]
    table_patterns: list[tuple[re.Pattern[str], str, str]]
    commodities: dict[str, str]
    attributes: dict[str, str]
    units: dict[str, tuple[str, str]]
    commodity_labels: dict[str, str] = field(default_factory=dict)
    attribute_labels: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Vocabulary:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            tables={label_key(k): (v["id"], v["label"]) for k, v in raw["tables"].items()},
            table_patterns=[
                (re.compile(p["pattern"], re.IGNORECASE), p["id"], p["label"])
                for p in raw.get("table_patterns", [])
            ],
            commodities={label_key(k): v for k, v in raw["commodities"].items()},
            attributes={label_key(k): v for k, v in raw["attributes"].items()},
            units={label_key(k): (v["id"], v["label"]) for k, v in raw["units"].items()},
            commodity_labels=raw.get("commodity_labels", {}),
            attribute_labels=raw.get("attribute_labels", {}),
        )

    def table(self, title: str) -> tuple[str, str, bool]:
        hit = self.tables.get(label_key(title))
        if hit:
            return (*hit, True)
        for pat, tid, lab in self.table_patterns:
            if pat.match(title):
                return tid, lab, True
        return slugify(title), title, False


def harmonize(raw: pd.DataFrame, vocab: Vocabulary) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (silver frame, unmapped-label report)."""
    df = raw.copy()
    unmapped: list[dict[str, str]] = []

    titles = {t: vocab.table(t) for t in df["report_title"].unique()}
    df["table_id"] = df["report_title"].map(lambda t: titles[t][0])
    df["table_label"] = df["report_title"].map(lambda t: titles[t][1])
    unmapped += [{"kind": "table", "label": t} for t, v in titles.items() if not v[2]]

    def mapper(col: str, table: dict[str, str], kind: str) -> pd.Series:
        uniq = df[col].unique()
        lut = {}
        for u in uniq:
            hit = table.get(label_key(u))
            if hit is None and u:
                unmapped.append({"kind": kind, "label": u})
            lut[u] = hit or slugify(u)
        return df[col].map(lut)

    df["commodity_id"] = mapper("commodity", vocab.commodities, "commodity")
    df["attribute_id"] = mapper("attribute", vocab.attributes, "attribute")
    df["region_id"] = df["region"].map(lambda r: slugify(r) if r else "united_states")
    df["region"] = df["region"].where(df["region"] != "", "United States")

    unit_lut = {}
    for u in df["unit"].unique():
        hit = vocab.units.get(label_key(u))
        if hit is None and u:
            unmapped.append({"kind": "unit", "label": u})
        unit_lut[u] = hit or (slugify(u) if u else "", u)
    df["unit_id"] = df["unit"].map(lambda u: unit_lut[u][0])
    df["unit_label"] = df["unit"].map(lambda u: unit_lut[u][1])

    df["commodity_label"] = df["commodity_id"].map(vocab.commodity_labels).fillna(df["commodity"])
    df["attribute_label"] = df["attribute_id"].map(vocab.attribute_labels).fillna(df["attribute"])
    df["my_start"] = pd.to_numeric(df["market_year"].str[:4], errors="coerce").astype("Int64")
    df["proj_est_flag"] = (
        df["proj_est_flag"].str.lower().str.strip(".() ").replace({"proj": "proj", "est": "est"})
    )
    df["reliability_stat"] = df["reliability_stat"].fillna("")

    # Within one report a key can repeat (sub-lines that share a label, e.g. sugar "Imports"
    # under TRQ and Other). Keep the first occurrence and number the rest so nothing is lost.
    # Exact repeats (same key and value, e.g. a country listed twice in old XML) are dropped.
    df = df.drop_duplicates([*SILVER_KEY, "value"]).copy()
    dup = df.groupby(SILVER_KEY, sort=False).cumcount()
    df.loc[dup > 0, "attribute_id"] = df.loc[dup > 0, "attribute_id"] + "_" + (dup[dup > 0] + 1).astype(str)

    report = (
        pd.DataFrame(unmapped, columns=["kind", "label"]).drop_duplicates().reset_index(drop=True)
        if unmapped
        else pd.DataFrame(columns=["kind", "label"])
    )
    return df, report


SILVER_COLUMNS = [
    "report_month",
    "wasde_number",
    "release_date",
    "source",
    "table_id",
    "table_label",
    "commodity_id",
    "commodity_label",
    "region_id",
    "region",
    "attribute_id",
    "attribute_label",
    "reliability_stat",
    "market_year",
    "my_start",
    "proj_est_flag",
    "period",
    "value",
    "unit_id",
    "unit_label",
]
