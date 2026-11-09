"""Common silver envelope: the columns every report's silver table starts with.

``report_id, release_key, release_ts_utc, edition, source, bronze_sha256, vintage_quality``
plus the shared value columns (``commodity_id, region_id, unit_id, value``) that each
report already carries. The envelope ties every silver row back to the exact bronze file
(and therefore the exact upstream bytes) it was parsed from.
"""

from __future__ import annotations

import pandas as pd

from usda_reports.core.manifest import ReleaseEntry

ENVELOPE_COLUMNS = [
    "report_id",
    "release_key",
    "release_ts_utc",
    "edition",
    "source",
    "bronze_sha256",
    "vintage_quality",
]
VALUE_COLUMNS = ["commodity_id", "region_id", "unit_id", "value"]
VINTAGE_QUALITY = ("as_published", "captured", "latest_only")


def add_envelope(
    df: pd.DataFrame,
    report_id: str,
    key_column: str,
    releases: dict[str, ReleaseEntry],
    vintage_quality: str = "as_published",
) -> pd.DataFrame:
    """Return ``df`` with the envelope columns first and every original column kept.

    ``key_column`` holds the release key of each row (``report_month`` for WASDE). The
    report's own ``source`` column is kept if present; otherwise it comes from the manifest.
    """
    if vintage_quality not in VINTAGE_QUALITY:
        raise ValueError(f"vintage_quality must be one of {VINTAGE_QUALITY}")
    keys = df[key_column].astype(str)
    meta = pd.DataFrame(
        [
            {
                "release_key": k,
                "release_ts_utc": e.release_ts_utc,
                "edition": e.edition,
                "manifest_source": e.source,
                "bronze_sha256": e.sha256,
            }
            for k, e in releases.items()
        ],
        columns=["release_key", "release_ts_utc", "edition", "manifest_source", "bronze_sha256"],
    ).set_index("release_key")
    env = pd.DataFrame(index=df.index)
    env["report_id"] = report_id
    env["release_key"] = keys
    env["release_ts_utc"] = pd.to_datetime(keys.map(meta["release_ts_utc"]), utc=True)
    env["edition"] = keys.map(meta["edition"]).fillna(1).astype("int32")
    env["source"] = df["source"] if "source" in df else keys.map(meta["manifest_source"])
    env["bronze_sha256"] = keys.map(meta["bronze_sha256"])
    env["vintage_quality"] = vintage_quality
    rest = df.drop(columns=[c for c in ENVELOPE_COLUMNS if c in df.columns])
    return pd.concat([env, rest], axis=1)
