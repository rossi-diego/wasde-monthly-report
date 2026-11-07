"""Learned translation from ESMIS XML positions to the CSV vocabulary.

Learning (dev-time, ``wasde learn-xml-layout``): for months where both the official CSV and
the XML exist (2021-01 → 2025-05), match each XML cell to the CSV row with the same market
year, value and attribute label. Votes are aggregated per XML *position*
(title, matrix, commodity cell, region cell) and the majority mapping is written to
``config/xml_layout/*.csv``, which is committed and reviewed like code.

Applying (every run): positions seen in the overlap map exactly; older positions (e.g. a
region that no longer exists) fall back to the (title, matrix, commodity) or
(title, matrix) group, keeping the region label from the XML.
"""

from __future__ import annotations

import collections
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from wasde.logs import get_logger
from wasde.silver.text import label_key

log = get_logger(__name__)

POS = ["xtitle", "matrix", "xcom", "xreg"]
TARGET = ["report_title", "commodity", "region"]


def _majority(counter: collections.Counter) -> tuple[tuple, int, int]:
    (best, n), total = counter.most_common(1)[0], sum(counter.values())
    return best, n, total


def learn(pairs: Iterable[tuple[pd.DataFrame, pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    """Learn layout tables from (xml cells frame, csv raw frame) month pairs."""
    pos_votes: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    pos_attr_votes: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    attr_votes: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    stats: collections.Counter = collections.Counter()

    for xml, csv in pairs:
        csv = csv[csv["reliability_stat"] == ""]
        index: dict[tuple, list[tuple]] = collections.defaultdict(list)
        for r in csv.itertuples(index=False):
            index[(r.market_year, round(r.value, 3), r.period)].append(
                (r.report_title, r.commodity, r.region, r.attribute)
            )
        for r in xml.itertuples(index=False):
            stats["cells"] += 1
            cands = index.get((r.market_year, round(r.value, 3), r.period), [])
            if not cands:
                stats["no_match"] += 1
                continue
            ak = label_key(r.xattr)
            same = [c for c in cands if label_key(c[3]) == ak] or cands
            if len(set(same)) != 1:
                stats["ambiguous"] += 1
                continue
            title, com, reg, attr = same[0]
            stats["matched"] += 1
            pos = (r.xtitle, r.matrix, r.xcom, r.xreg)
            pos_votes[pos][(title, com, reg)] += 1
            pos_attr_votes[(*pos, r.xattr)][(title, com, reg)] += 1
            attr_votes[(title, r.xattr)][attr] += 1

    positions, pos_attrs = [], []
    for pos, cnt in pos_votes.items():
        best, n, total = _majority(cnt)
        if n < 3:
            continue
        share = n / total
        positions.append((*pos, *best, n, round(share, 3)))
        if share < 0.9:
            for (p0, p1, p2, p3, xattr), c2 in pos_attr_votes.items():
                if (p0, p1, p2, p3) == pos:
                    b2, n2, _ = _majority(c2)
                    if n2 >= 2:
                        pos_attrs.append((*pos, xattr, *b2, n2))
    attributes = []
    for (title, xattr), cnt in attr_votes.items():
        best_attr, n, total = _majority(cnt)
        if n >= 2:
            attributes.append((title, xattr, best_attr, n, round(n / total, 3)))

    log.info("xml_layout.learned", **stats, positions=len(positions), attributes=len(attributes))
    return {
        "positions": pd.DataFrame(positions, columns=[*POS, *TARGET, "votes", "share"]),
        "position_attributes": pd.DataFrame(pos_attrs, columns=[*POS, "xattr", *TARGET, "votes"]),
        "attributes": pd.DataFrame(
            attributes, columns=["report_title", "xattr", "attribute", "votes", "share"]
        ),
        "_stats": pd.DataFrame([stats]),
    }


def learn_units(csv_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Unit per (title, commodity, attribute), taken from the most recent CSV that has it."""
    frames = [f[f["reliability_stat"] == ""] for f in csv_frames]
    df = pd.concat(frames, ignore_index=True).sort_values("report_month")
    units = df.groupby(["report_title", "commodity", "attribute"], as_index=False)["unit"].last()
    return units


@dataclass
class XmlLayout:
    positions: pd.DataFrame
    position_attributes: pd.DataFrame
    attributes: pd.DataFrame
    units: pd.DataFrame
    title_aliases: dict[str, str] = field(default_factory=dict)
    commodity_aliases: dict[str, str] = field(default_factory=dict)
    stats: collections.Counter = field(default_factory=collections.Counter)

    # ── persistence ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, folder: Path) -> XmlLayout:
        def read(name: str) -> pd.DataFrame:
            return pd.read_csv(folder / f"{name}.csv", dtype=str, keep_default_na=False)

        aliases_path = folder / "aliases.yaml"
        aliases = (
            yaml.safe_load(aliases_path.read_text(encoding="utf-8"))
            if aliases_path.exists()
            else {}
        ) or {}
        return cls(
            positions=read("positions"),
            position_attributes=read("position_attributes"),
            attributes=read("attributes"),
            units=read("units"),
            title_aliases=aliases.get("titles") or {},
            commodity_aliases=aliases.get("commodities") or {},
        )

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("positions", "position_attributes", "attributes", "units"):
            df: pd.DataFrame = getattr(self, name)
            df.sort_values(list(df.columns[:4])).to_csv(folder / f"{name}.csv", index=False)

    # ── application ──────────────────────────────────────────────────────────

    def _lookups(self) -> None:
        if hasattr(self, "_pos"):
            return
        self._pos = {
            tuple(r[:4]): tuple(r[4:7])
            for r in self.positions[[*POS, *TARGET]].itertuples(index=False)
        }
        self._pos_attr = {
            tuple(r[:5]): tuple(r[5:8])
            for r in self.position_attributes[[*POS, "xattr", *TARGET]].itertuples(index=False)
        }
        # Group fallbacks: only when >=95% of the group's votes agree on (title, commodity).
        self._group3: dict[tuple, tuple[str, str, str | None]] = {}
        self._group2: dict[tuple, tuple[str, str, str | None]] = {}
        pos = self.positions.assign(votes=pd.to_numeric(self.positions["votes"]))
        for keys, store in (
            (["xtitle", "matrix", "xcom"], self._group3),
            (["xtitle", "matrix"], self._group2),
        ):
            for k, g in pos.groupby(keys):
                tc = g.groupby(["report_title", "commodity"])["votes"].sum().sort_values()
                if tc.iloc[-1] / tc.sum() < 0.95:
                    continue
                title, com = tc.index[-1]
                regions = g.loc[(g.report_title == title) & (g.commodity == com), "region"].unique()
                store[k if isinstance(k, tuple) else (k,)] = (
                    title,
                    com,
                    regions[0] if len(regions) == 1 else None,
                )
        self._attr = {
            (r.report_title, r.xattr): r.attribute for r in self.attributes.itertuples(index=False)
        }
        vocab: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for r in self.attributes.itertuples(index=False):
            vocab[label_key(r.xattr)][r.attribute] += int(r.votes or 1)
        for a in self.units["attribute"].unique():
            vocab[label_key(a)][a] += 1
        self._attr_vocab = {k: c.most_common(1)[0][0] for k, c in vocab.items()}
        u = self.units
        self._unit3 = {
            (r.report_title, r.commodity, r.attribute): r.unit for r in u.itertuples(index=False)
        }
        self._unit2 = (
            u.groupby(["report_title", "attribute"])["unit"]
            .agg(lambda s: s.mode().iat[0])
            .to_dict()
        )
        per_title = u.groupby("report_title")["unit"].agg(lambda s: s.unique().tolist())
        self._unit1 = {t: us[0] for t, us in per_title.items() if len(us) == 1}

    def _map_position(
        self, xtitle: str, matrix: str, xcom: str, xreg: str, xattr: str
    ) -> tuple | None:
        xtitle = self.title_aliases.get(xtitle, xtitle)
        xcom = self.commodity_aliases.get(xcom, xcom)
        hit = self._pos_attr.get((xtitle, matrix, xcom, xreg, xattr)) or self._pos.get(
            (xtitle, matrix, xcom, xreg)
        )
        if hit:
            self.stats["exact"] += 1
            return hit
        for key, store, kind in (
            ((xtitle, matrix, xcom), self._group3, "group3"),
            ((xtitle, matrix), self._group2, "group2"),
        ):
            g = store.get(key)
            if g:
                title, com, reg = g
                self.stats[kind] += 1
                return title, com, reg or xreg
        self.stats["unmapped"] += 1
        return None

    def _map_attribute(self, title: str, xattr: str) -> str:
        return self._attr.get((title, xattr)) or self._attr_vocab.get(label_key(xattr)) or xattr

    def _map_unit(self, title: str, com: str, attr: str, subtitle: str) -> str:
        return (
            self._unit3.get((title, com, attr))
            or self._unit2.get((title, attr))
            or self._unit1.get(title)
            or subtitle
        )

    def apply(self, frame: pd.DataFrame) -> pd.DataFrame:
        self._lookups()
        out = []
        for r in frame.itertuples(index=False):
            hit = self._map_position(r.xtitle, r.matrix, r.xcom, r.xreg, r.xattr)
            if hit is None:
                continue
            title, com, reg = hit
            attr = self._map_attribute(title, r.xattr)
            out.append(
                {
                    "report_title": title,
                    "commodity": com,
                    "region": reg,
                    "attribute": attr,
                    "market_year": r.market_year,
                    "proj_est_flag": r.proj_est_flag,
                    "period": r.period,
                    "value": r.value,
                    "unit": self._map_unit(title, com, attr, r.subtitle),
                }
            )
        return pd.DataFrame(out)
