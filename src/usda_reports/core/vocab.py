"""Shared vocabularies (``config/vocab/*.yaml``): one canonical id per commodity/region/…

Every report maps its own labels onto these ids. Resolution is strict: an unseen label
raises :class:`UnseenLabelError`, so a new upstream label fails only that report's build
instead of silently creating a new series. (WASDE's richer table/attribute mapping lives in
``config/reports/wasde/mappings.yaml`` and reports unmapped labels the same way.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class UnseenLabelError(KeyError):
    """A source label is not in the vocabulary."""


def label_key(s: str) -> str:
    """Case/space/punctuation-insensitive key."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


@dataclass
class Vocab:
    kind: str
    labels: dict[str, str]  # canonical id -> display label
    aliases: dict[str, str] = field(default_factory=dict)  # label_key(alias) -> id

    @classmethod
    def load(cls, path: Path) -> Vocab:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        labels: dict[str, str] = {}
        aliases: dict[str, str] = {}
        for vid, spec in raw["items"].items():
            labels[vid] = spec["label"]
            for alias in [vid, spec["label"], *spec.get("aliases", [])]:
                k = label_key(str(alias))
                if k in aliases and aliases[k] != vid:
                    raise ValueError(f"{path.name}: alias {alias!r} maps to {aliases[k]} and {vid}")
                aliases[k] = vid
        return cls(kind=raw.get("kind", path.stem), labels=labels, aliases=aliases)

    def ids(self) -> set[str]:
        return set(self.labels)

    def resolve(self, label: str) -> str:
        try:
            return self.aliases[label_key(label)]
        except KeyError as exc:
            raise UnseenLabelError(f"unseen {self.kind} label {label!r}") from exc

    def unseen(self, labels: list[str]) -> list[str]:
        return sorted({lab for lab in labels if label_key(lab) not in self.aliases})
