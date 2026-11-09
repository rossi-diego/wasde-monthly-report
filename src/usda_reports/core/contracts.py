"""Silver contracts runner: ``config/contracts/<report_id>.yaml`` checked on every build.

A contract is a cheap guard against a silently broken parse. It checks, per report:
not-null columns, a unique key, a minimum row count per release, rows that must exist in
every release (e.g. U.S. corn ending stocks in every WASDE) and, when ``envelope: true``,
the common silver envelope columns and their allowed values.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from usda_reports.silver.envelope import ENVELOPE_COLUMNS, VINTAGE_QUALITY


class ContractError(ValueError):
    """Silver data violates its report contract."""


class RequiredRows(BaseModel):
    label: str = "required rows"
    filter: dict[str, str] = Field(default_factory=dict)
    columns: list[str]
    rows: list[list[str]]

    def tuples(self) -> list[tuple[str, ...]]:
        return [tuple(r) for r in self.rows]


class Contract(BaseModel):
    report_id: str
    release_column: str
    release_label: str = "releases"
    key: list[str] = Field(default_factory=list)
    not_null: list[str] = Field(default_factory=list)
    min_rows_per_release: int = 0
    required_per_release: RequiredRows | None = None
    envelope: bool = True

    @classmethod
    def load(cls, path: Path) -> Contract:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def check(
        self, df: pd.DataFrame, min_rows: int | None = None, envelope: bool | None = None
    ) -> list[str]:
        """Return every violation (empty list = contract holds)."""
        errors: list[str] = []
        min_rows = self.min_rows_per_release if min_rows is None else min_rows
        check_envelope = self.envelope if envelope is None else envelope
        if check_envelope:
            missing = [c for c in ENVELOPE_COLUMNS if c not in df.columns]
            if missing:
                errors.append(f"missing envelope columns {missing}")
            else:
                bad_ids = set(df["report_id"].unique()) - {self.report_id}
                if bad_ids:
                    errors.append(f"unexpected report_id values {sorted(bad_ids)}")
                bad_vq = set(df["vintage_quality"].unique()) - set(VINTAGE_QUALITY)
                if bad_vq:
                    errors.append(f"unexpected vintage_quality values {sorted(bad_vq)}")
                for col in ("release_key", "release_ts_utc", "bronze_sha256"):
                    n = int(df[col].isna().sum())
                    if n:
                        errors.append(f"{n} null values in {col}")
        for col in self.not_null:
            n = int(df[col].isna().sum())
            if n:
                errors.append(f"{n} null values in {col}")
        if self.key:
            dups = int(df.duplicated(self.key).sum())
            if dups:
                errors.append(f"{dups} duplicate silver keys")
        counts = df.groupby(self.release_column).size()
        small = counts[counts < min_rows]
        if len(small):
            errors.append(f"{self.release_label} below {min_rows} rows: {small.to_dict()}")
        req = self.required_per_release
        if req is not None:
            sub = df
            for col, val in req.filter.items():
                sub = sub[sub[col] == val]
            present = set(
                sub[[self.release_column, *req.columns]]
                .drop_duplicates()
                .itertuples(index=False, name=None)
            )
            for release in counts.index:
                missing_rows = [r for r in req.tuples() if (release, *r) not in present]
                if missing_rows:
                    errors.append(f"{release}: missing {req.label} {missing_rows}")
        return errors

    def enforce(
        self, df: pd.DataFrame, min_rows: int | None = None, envelope: bool | None = None
    ) -> None:
        errors = self.check(df, min_rows=min_rows, envelope=envelope)
        if errors:
            raise ContractError("; ".join(errors[:20]))
