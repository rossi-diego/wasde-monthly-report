"""FAS Export Sales (ESR) API client: discover the newest release, pull exports per
commodity × marketing year, and pack every pull into one deterministic bronze bundle.

* Host ``api.fas.usda.gov`` (pinned in ``config/reports/export_sales/source.yaml``); the key
  goes in the ``X-Api-Key`` header and is never logged. ``FAS_API_KEY`` is read first, then
  ``USDA_PSD_KEY`` (same api.data.gov key).
* Calls are serialized with a minimum interval (api.data.gov: 1,000 requests/hour per key);
  429 and 5xx answers are retried with exponential backoff, honouring ``Retry-After``.
* A pull is stored byte-for-byte as gzip JSON with sorted keys and ``mtime=0``, so the same
  upstream content always hashes to the same sha256.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from usda_reports.core.logs import get_logger

log = get_logger(__name__)

REPORT_ID = "export_sales"
SOURCE = "fas_esr_api"
BUNDLE_SCHEMA = 1


class EsrError(RuntimeError):
    """The ESR API answered with something we cannot use."""


class MissingKeyError(EsrError):
    pass


class CommodityRef(BaseModel):
    code: int
    esr_name: str


class UnitRef(BaseModel):
    esr_unit_id: int
    esr_unit_name: str
    unit_id: str


class SourceConfig(BaseModel):
    api_base: str
    key_env: list[str]
    endpoints: dict[str, str]
    min_interval_s: float = 1.5
    history_start_market_year: int = 2011
    previous_my_weeks: int = 8
    unit: UnitRef
    commodities: dict[str, CommodityRef]
    metrics: dict[str, str]
    countries: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> SourceConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def code_to_commodity(self) -> dict[int, str]:
        return {c.code: cid for cid, c in self.commodities.items()}

    def api_key(self, env: dict[str, str] | None = None) -> str:
        env = dict(os.environ) if env is None else env
        for name in self.key_env:
            if env.get(name):
                return env[name]
        raise MissingKeyError(f"no ESR API key: set one of {self.key_env}")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(min(int(retry_after), 120))
        return code == 429 or code >= 500
    return isinstance(exc, httpx.TransportError)


@dataclass
class EsrClient:
    """Serialized ESR API access. ``calls`` counts requests (rate-limit budget)."""

    client: httpx.Client
    config: SourceConfig
    api_key: str = field(repr=False)
    calls: int = 0
    _last: float = field(default=0.0, repr=False)

    def _wait(self) -> None:
        gap = self.config.min_interval_s - (time.monotonic() - self._last)
        if gap > 0 and self._last:
            time.sleep(gap)
        self._last = time.monotonic()

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        reraise=True,
    )
    def get_json(self, path: str) -> Any:
        self._wait()
        self.calls += 1
        resp = self.client.get(
            self.config.api_base + path,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
        )
        if resp.status_code in (401, 403):
            # Never include headers in the message: they carry the key.
            raise EsrError(f"ESR API refused {path} with HTTP {resp.status_code} (key invalid?)")
        resp.raise_for_status()
        remaining = resp.headers.get("X-RateLimit-Remaining")
        log.info("esr.get", path=path, status=resp.status_code, rate_remaining=remaining)
        if remaining is not None and remaining.isdigit() and int(remaining) < 25:
            raise EsrError(f"api.data.gov rate limit nearly exhausted ({remaining} left)")
        try:
            return resp.json()
        except ValueError as exc:
            raise EsrError(f"{path}: response is not JSON") from exc

    def exports(self, code: int, market_year: int) -> list[dict[str, Any]]:
        path = self.config.endpoints["exports"].format(code=code, market_year=market_year)
        data = self.get_json(path)
        if not isinstance(data, list):
            raise EsrError(f"{path}: expected a JSON list")
        return data


# ── release discovery ────────────────────────────────────────────────────────

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})")


@dataclass(frozen=True)
class EsrRelease:
    """The newest ESR release as reported by ``/api/esr/datareleasedates``."""

    release_key: str  # YYYY-MM-DD (ET date of releaseTimeStamp)
    release_time_et: str  # HH:MM
    market_years: dict[str, int]  # commodity_id -> current ESR marketYear
    my_starts: dict[str, str]  # commodity_id -> marketYearStart (YYYY-MM-DD)
    rows: tuple[dict[str, Any], ...] = ()


def parse_release_dates(rows: list[dict[str, Any]], config: SourceConfig) -> EsrRelease:
    """Newest release across the configured commodities (all share one release time)."""
    by_code = config.code_to_commodity()
    mine = [r for r in rows if int(r.get("commodityCode", -1)) in by_code]
    missing = set(by_code) - {int(r["commodityCode"]) for r in mine}
    if missing:
        raise EsrError(f"datareleasedates has no row for commodity codes {sorted(missing)}")
    stamps = []
    for r in mine:
        m = _TS_RE.match(str(r.get("releaseTimeStamp") or ""))
        if not m:
            raise EsrError(f"unparseable releaseTimeStamp {r.get('releaseTimeStamp')!r}")
        stamps.append((m[1], f"{m[2]}:{m[3]}"))
    key, at = max(stamps)
    return EsrRelease(
        release_key=key,
        release_time_et=at,
        market_years={by_code[int(r["commodityCode"])]: int(r["marketYear"]) for r in mine},
        my_starts={by_code[int(r["commodityCode"])]: str(r["marketYearStart"])[:10] for r in mine},
        rows=tuple(sorted(mine, key=lambda r: int(r["commodityCode"]))),
    )


def verify_lookups(
    commodities: list[dict[str, Any]], units: list[dict[str, Any]], config: SourceConfig
) -> list[str]:
    """Problems with the configured codes vs ``/api/esr/commodities`` and units (empty = ok)."""
    problems = []
    names = {int(c["commodityCode"]): c for c in commodities}
    for cid, ref in config.commodities.items():
        got = names.get(ref.code)
        if got is None:
            problems.append(f"{cid}: code {ref.code} not in /api/esr/commodities")
            continue
        if str(got.get("commodityName", "")).strip() != ref.esr_name:
            problems.append(
                f"{cid}: code {ref.code} is {got.get('commodityName')!r}, expected {ref.esr_name!r}"
            )
        if int(got.get("unitId", -1)) != config.unit.esr_unit_id:
            problems.append(f"{cid}: unitId {got.get('unitId')} != {config.unit.esr_unit_id}")
    unit_names = {int(u["unitId"]): str(u.get("unitNames", "")).strip() for u in units}
    if unit_names.get(config.unit.esr_unit_id) != config.unit.esr_unit_name:
        problems.append(
            f"unitId {config.unit.esr_unit_id} is {unit_names.get(config.unit.esr_unit_id)!r}, "
            f"expected {config.unit.esr_unit_name!r}"
        )
    return problems


# ── bundles (bronze) ─────────────────────────────────────────────────────────


def market_years_to_pull(
    release: EsrRelease,
    config: SourceConfig,
    kind: str,
    today: date,
) -> dict[str, list[int]]:
    """ESR marketYears per commodity for one pull.

    ``backfill``: every MY from ``history_start_market_year`` to the current one.
    ``weekly``: the current MY, plus the previous one during the first weeks of a new MY.
    """
    out: dict[str, list[int]] = {}
    for cid in config.commodities:
        cur = release.market_years[cid]
        if kind == "backfill":
            out[cid] = list(range(config.history_start_market_year, cur + 1))
            continue
        years = [cur]
        start = date.fromisoformat(release.my_starts[cid])
        if (today - start).days < 7 * config.previous_my_weeks:
            years.insert(0, cur - 1)
        out[cid] = years
    return out


def pull(
    esr: EsrClient,
    release: EsrRelease,
    kind: str,
    today: date,
) -> dict[str, Any]:
    """Fetch every commodity × MY for one pull and return the bundle (bronze payload)."""
    plan = market_years_to_pull(release, esr.config, kind, today)
    responses = []
    for cid, years in plan.items():
        code = esr.config.commodities[cid].code
        for my in years:
            records = esr.exports(code, my)
            responses.append(
                {
                    "commodity_code": code,
                    "market_year": my,
                    "path": esr.config.endpoints["exports"].format(code=code, market_year=my),
                    "records": records,
                }
            )
    log.info("esr.pulled", kind=kind, release=release.release_key, calls=esr.calls)
    return make_bundle(release, kind, responses)


def make_bundle(release: EsrRelease, kind: str, responses: list[dict[str, Any]]) -> dict[str, Any]:
    if kind not in ("backfill", "weekly"):
        raise ValueError(f"unknown pull kind {kind!r}")
    return {
        "schema": BUNDLE_SCHEMA,
        "report_id": REPORT_ID,
        "kind": kind,
        "release_key": release.release_key,
        "release_time_et": release.release_time_et,
        "datareleasedates": list(release.rows),
        "responses": sorted(responses, key=lambda r: (r["commodity_code"], r["market_year"])),
    }


def encode_bundle(bundle: dict[str, Any]) -> bytes:
    """Deterministic bytes: sorted keys, compact separators, gzip with mtime=0."""
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=6, mtime=0)


def decode_bundle(data: bytes) -> dict[str, Any]:
    raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    bundle: dict[str, Any] = json.loads(raw.decode("utf-8"))
    if bundle.get("schema") != BUNDLE_SCHEMA or bundle.get("report_id") != REPORT_ID:
        raise EsrError("not an export_sales bronze bundle")
    return bundle


def newest_week(bundle: dict[str, Any]) -> str | None:
    """Latest weekEndingDate (YYYY-MM-DD) in the bundle's current-MY responses."""
    weeks = [str(r["weekEndingDate"])[:10] for resp in bundle["responses"] for r in resp["records"]]
    return max(weeks) if weeks else None


def countries_vocab(countries: list[dict[str, Any]]) -> dict[str, Any]:
    """``config/vocab/countries.yaml`` body from ``/api/esr/countries`` (id = slug of name).

    The short ids below were checked against the 2026-11-09 lookup (code → description)."""
    labels = {5700: "China", 9990: "Unknown destinations", 1: "European Union"}
    overrides = {
        1: "european_union",
        5700: "china",
        9990: "unknown",
        5820: "hong_kong",
        5830: "taiwan",
        5800: "south_korea",
        5790: "north_korea",
        4621: "russia",
        1220: "canada",
        2010: "mexico",
    }
    items: dict[str, dict[str, Any]] = {}
    for c in sorted(countries, key=lambda c: int(c["countryCode"])):
        code = int(c["countryCode"])
        label = " ".join(str(c.get("countryDescription") or c.get("countryName")).split())
        cid = overrides.get(code) or re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        if cid in items:
            cid = f"{cid}_{code}"
        items[cid] = {
            "label": labels.get(code) or (label.title() if label.isupper() else label),
            "code": code,
            "genc": c.get("gencCode"),
            "esr_region_id": c.get("regionId"),
            "aliases": [f"esr:{code}"],
        }
    return {
        "kind": "country",
        "source": "FAS ESR /api/esr/countries",
        "fetched": datetime.now().date().isoformat(),
        "items": items,
    }
