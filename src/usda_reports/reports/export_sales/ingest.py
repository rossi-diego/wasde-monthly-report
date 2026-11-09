"""Export Sales ingest: one-time backfill and the weekly pull, both into bronze.

* **Backfill** (no ESR release in the manifest yet): every marketing year from 2010/11 to the
  current one for the configured commodities, one request per commodity × MY (about 85 calls
  plus 3 lookups). Stored as one snapshot with ``kind: backfill`` (``vintage_quality =
  latest_only``: the API returns today's revised values for old weeks).
* **Weekly**: when ``/api/esr/datareleasedates`` shows a release newer than the manifest, pull
  the current MY (plus the previous one early in a new MY) — ``kind: weekly``, ``captured``.
  Re-pulling the same release only stores a new edition when the bytes changed.

A pulled bundle is parsed and contract-checked (``check``) *before* it reaches bronze: an
unseen destination code or a contract break fails the ingest with :class:`EsrError` and
leaves bronze and the manifest as they were, so the last good ESR state keeps building.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from usda_reports.bronze.store import BronzeStore, sha256
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import release_ts_utc
from usda_reports.reports.export_sales.source import (
    SOURCE,
    EsrClient,
    EsrError,
    EsrRelease,
    encode_bundle,
    newest_week,
    parse_release_dates,
    pull,
    verify_lookups,
)

log = get_logger(__name__)


@dataclass
class IngestResult:
    ingested: list[str] = field(default_factory=list)  # release keys new or changed in bronze
    release: EsrRelease | None = None
    calls: int = 0
    note: str = ""


def discover(esr: EsrClient) -> EsrRelease:
    rows = esr.get_json(esr.config.endpoints["release_dates"])
    if not isinstance(rows, list):
        raise EsrError("datareleasedates: expected a JSON list")
    return parse_release_dates(rows, esr.config)


def check_codes(esr: EsrClient) -> None:
    """Fail fast when a configured commodity code no longer means what config says."""
    commodities = esr.get_json(esr.config.endpoints["commodities"])
    units = esr.get_json(esr.config.endpoints["units"])
    problems = verify_lookups(commodities, units, esr.config)
    if problems:
        raise EsrError("ESR lookup check failed: " + "; ".join(problems))


def _store(
    store: BronzeStore, release: EsrRelease, bundle: dict[str, Any], url: str
) -> tuple[bool, str]:
    """Write the bundle unless the same release already holds identical bytes."""
    data = encode_bundle(bundle)
    key = release.release_key
    old = store.entries.get(key)
    if old is not None and old.status == "ok" and old.sha256 == sha256(data):
        return False, key
    edition = (old.edition + 1) if old is not None and old.status == "ok" else 1
    store.put(key, data, source=SOURCE, url=url, release_date=key, edition=edition)
    # The API's own release time wins over the configured 08:30 when they differ.
    entry = store.entries[key]
    entry.release_ts_utc = release_ts_utc(key, release.release_time_et)
    return True, key


def ingest(
    esr: EsrClient,
    store: BronzeStore,
    now: datetime | None = None,
    force: bool = False,
    check: Callable[[dict[str, Any]], None] | None = None,
) -> IngestResult:
    """Backfill when bronze has no ESR snapshot yet, else pull the newest release if new.

    ``check(bundle)`` validates the pull before it is stored (raises :class:`EsrError`)."""
    now = now or datetime.now(UTC)
    result = IngestResult()
    have = {k for k, e in store.entries.items() if e.status == "ok"}
    release = discover(esr)
    result.release = release
    kind = "weekly" if have else "backfill"
    if kind == "weekly" and release.release_key in have and not force:
        result.note = "release already ingested"
        result.calls = esr.calls
        log.info("esr.up_to_date", release=release.release_key)
        return result
    if kind == "backfill":
        check_codes(esr)
    bundle = pull(esr, release, kind, now.date())
    week = newest_week(bundle)
    if week is None:
        raise EsrError(f"release {release.release_key}: the API returned no records")
    lag = (date.fromisoformat(release.release_key) - date.fromisoformat(week)).days
    if not 5 <= lag <= 14:
        raise EsrError(
            f"release {release.release_key}: newest week {week} is {lag} days earlier "
            "(expected the week that ended the previous Thursday)"
        )
    if check is not None:
        check(bundle)  # raises EsrError: nothing is written to bronze
    changed, key = _store(store, release, bundle, esr.config.api_base)
    if changed:
        result.ingested.append(key)
    result.calls = esr.calls
    log.info(
        "esr.ingested" if changed else "esr.unchanged",
        kind=kind,
        release=key,
        newest_week=week,
        calls=esr.calls,
    )
    return result
