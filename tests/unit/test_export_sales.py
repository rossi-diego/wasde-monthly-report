"""Export Sales: API client (mocked, no key, no network), bundles and the silver parser.

Fixtures in tests/fixtures/export_sales/ are trimmed real API responses (2026-11-09 spike):
``bundle_2025-09-11.json`` is what a pull on 2025-09-11 returns for 4 destinations.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime

import httpx
import pandas as pd
import pytest
import respx

from usda_reports.bronze.store import BronzeStore
from usda_reports.core.calendar import load_calendar_raw
from usda_reports.core.config import Settings
from usda_reports.core.contracts import Contract, ContractError
from usda_reports.core.manifest import Manifest
from usda_reports.core.vocab import UnseenLabelError, Vocab
from usda_reports.reports.export_sales import ingest as esr_ingest
from usda_reports.reports.export_sales.parse import (
    Snapshot,
    build_frame,
    market_year_label,
    my_start_months,
    validate,
    week_of_my,
)
from usda_reports.reports.export_sales.source import (
    EsrClient,
    EsrError,
    MissingKeyError,
    SourceConfig,
    decode_bundle,
    encode_bundle,
    market_years_to_pull,
    newest_week,
    parse_release_dates,
    verify_lookups,
)

FAKE_KEY = "test-key-not-real"


@pytest.fixture
def cfg(config_dir) -> SourceConfig:
    c = SourceConfig.load(config_dir / "reports" / "export_sales" / "source.yaml")
    return c.model_copy(update={"min_interval_s": 0.0})


@pytest.fixture
def esr_fx(fixtures):
    return fixtures / "export_sales"


@pytest.fixture
def bundle(esr_fx) -> dict:
    return json.loads((esr_fx / "bundle_2025-09-11.json").read_text(encoding="utf-8"))


@pytest.fixture
def parse_ctx(config_dir):
    root = config_dir.parent
    return {
        "countries": Vocab.load(config_dir / "vocab" / "countries.yaml"),
        "starts": my_start_months(root / "dbt" / "seeds" / "dim_commodity.csv"),
        "calendar": load_calendar_raw(config_dir / "calendars" / "export_sales.yaml"),
    }


# ── config, codes, key ───────────────────────────────────────────────────────


def test_verified_codes_match_the_lookup(cfg, esr_fx):
    commodities = json.loads((esr_fx / "commodities.json").read_text())
    units = json.loads((esr_fx / "units.json").read_text())
    assert verify_lookups(commodities, units, cfg) == []
    assert {c: r.code for c, r in cfg.commodities.items()} == {
        "soybeans": 801,
        "corn": 401,
        "wheat": 107,
        "soybean_meal": 901,
        "soybean_oil": 902,
    }
    renamed = [
        dict(c, commodityName="Wheat - HRW") if c["commodityCode"] == 107 else c
        for c in commodities
    ]
    problems = verify_lookups(renamed, units, cfg)
    assert problems and "wheat: code 107" in problems[0]


def test_api_key_order_and_missing(cfg):
    assert cfg.api_key({"FAS_API_KEY": "a", "USDA_PSD_KEY": "b"}) == "a"
    assert cfg.api_key({"USDA_PSD_KEY": "b"}) == "b"
    with pytest.raises(MissingKeyError):
        cfg.api_key({})


def test_release_dates_and_market_year_plan(cfg, esr_fx):
    rel = parse_release_dates(json.loads((esr_fx / "datareleasedates.json").read_text()), cfg)
    assert rel.release_key == "2026-11-05" and rel.release_time_et == "08:30"
    assert rel.market_years == {
        "soybeans": 2027,
        "corn": 2027,
        "wheat": 2027,
        "soybean_meal": 2027,
        "soybean_oil": 2027,
    }
    backfill = market_years_to_pull(rel, cfg, "backfill", date(2026, 11, 9))
    assert sum(len(v) for v in backfill.values()) == 85  # 5 commodities × MY 2011..2027
    weekly = market_years_to_pull(rel, cfg, "weekly", date(2026, 11, 9))
    # Meal/oil MY started 2026-10-01 (< 8 weeks ago): previous MY pulled too.
    assert weekly["soybean_meal"] == [2026, 2027] and weekly["corn"] == [2027]


def test_market_year_and_week_index():
    assert market_year_label(2027) == "2026/27"
    assert market_year_label(2001) == "2000/01"
    assert week_of_my(date(2026, 9, 3), date(2026, 9, 1)) == 1
    assert week_of_my(date(2026, 10, 29), date(2026, 9, 1)) == 9


# ── client: serialized, retried, key never leaks ─────────────────────────────


@respx.mock
def test_client_sends_key_header_and_retries_429(cfg, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    route = respx.get("https://api.fas.usda.gov/api/esr/datareleasedates").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json=[], headers={"X-RateLimit-Remaining": "900"}),
        ]
    )
    with httpx.Client() as c:
        esr = EsrClient(c, cfg, FAKE_KEY)
        assert esr.get_json("/api/esr/datareleasedates") == []
    assert route.call_count == 2
    assert route.calls[0].request.headers["X-Api-Key"] == FAKE_KEY
    assert FAKE_KEY not in str(route.calls[0].request.url)


@respx.mock
def test_refused_key_error_never_contains_the_key(cfg):
    respx.get("https://api.fas.usda.gov/api/esr/commodities").mock(
        return_value=httpx.Response(403, text="API_KEY_INVALID")
    )
    with httpx.Client() as c, pytest.raises(EsrError) as exc:
        EsrClient(c, cfg, FAKE_KEY).get_json("/api/esr/commodities")
    assert FAKE_KEY not in str(exc.value) and "403" in str(exc.value)


@respx.mock
def test_ingest_weekly_pull_stores_one_snapshot(cfg, esr_fx, bundle, tmp_path, monkeypatch):
    """With a snapshot already in bronze, a newer release triggers a weekly pull; the same
    release again is a no-op without any exports call."""
    monkeypatch.setattr("time.sleep", lambda s: None)
    rd = json.loads((esr_fx / "datareleasedates.json").read_text())
    respx.get("https://api.fas.usda.gov/api/esr/datareleasedates").mock(
        return_value=httpx.Response(200, json=rd)
    )
    week = {
        "commodityCode": 0,
        "countryCode": 5700,
        "weeklyExports": 1.0,
        "accumulatedExports": 2.0,
        "outstandingSales": 3.0,
        "grossNewSales": 0,
        "currentMYNetSales": 4.0,
        "currentMYTotalCommitment": 5.0,
        "nextMYOutstandingSales": 0,
        "nextMYNetSales": 0,
        "unitId": 1,
        "weekEndingDate": "2026-10-29T00:00:00",
    }
    exports = respx.get(url__regex=r".*/api/esr/exports/.*").mock(
        side_effect=lambda req: httpx.Response(
            200, json=[dict(week, commodityCode=int(req.url.path.split("/")[5]))]
        )
    )
    manifest = Manifest()
    store = BronzeStore(tmp_path, manifest, "export_sales", "08:30")
    store.put(
        "2026-10-29",
        encode_bundle(bundle),
        source="fas_esr_api",
        url="x",
        release_date="2026-10-29",
    )
    with httpx.Client() as c:
        esr = EsrClient(c, cfg, FAKE_KEY)
        res = esr_ingest.ingest(esr, store, datetime(2026, 11, 9, tzinfo=UTC))
        assert res.ingested == ["2026-11-05"]
        assert exports.call_count == 7  # 5 current MYs + previous MY of meal and oil
        entry = manifest.releases("export_sales")["2026-11-05"]
        assert entry.file == "export_sales/2026-11-05.json.gz"
        assert entry.release_ts_utc == "2026-11-05T13:30:00+00:00"
        stored = decode_bundle((tmp_path / entry.file).read_bytes())
        assert stored["kind"] == "weekly" and newest_week(stored) == "2026-10-29"
        again = esr_ingest.ingest(esr, store, datetime(2026, 11, 9, 1, tzinfo=UTC))
        assert again.ingested == [] and exports.call_count == 7


@respx.mock
@pytest.mark.parametrize("country", [5700, 99999])
def test_ingest_rejects_unseen_country_before_bronze(
    cfg, esr_fx, bundle, tmp_path, monkeypatch, config_dir, country
):
    """The spec's check parses and contract-checks the pull before storing it: an unseen
    destination code raises EsrError (detect fails, alert issue) and bronze is untouched."""
    from usda_reports.core.registry import load_registry

    monkeypatch.setattr("time.sleep", lambda s: None)
    rd = json.loads((esr_fx / "datareleasedates.json").read_text())
    respx.get("https://api.fas.usda.gov/api/esr/datareleasedates").mock(
        return_value=httpx.Response(200, json=rd)
    )
    rec = {
        "countryCode": country,
        "weeklyExports": 1.0,
        "accumulatedExports": 2.0,
        "outstandingSales": 3.0,
        "grossNewSales": 0,
        "currentMYNetSales": 4.0,
        "currentMYTotalCommitment": 5.0,
        "nextMYOutstandingSales": 0,
        "nextMYNetSales": 0,
        "unitId": 1,
        "weekEndingDate": "2026-10-29T00:00:00",
    }
    respx.get(url__regex=r".*/api/esr/exports/.*").mock(
        side_effect=lambda req: httpx.Response(
            200, json=[dict(rec, commodityCode=int(req.url.path.split("/")[5]))]
        )
    )
    spec = load_registry(config_dir).spec(
        "export_sales", Settings(_env_file=None, config_dir=config_dir)
    )
    manifest = Manifest()
    store = BronzeStore(tmp_path, manifest, "export_sales", "08:30")
    store.put("2026-10-29", encode_bundle(bundle), source="fas_esr_api", url="x")
    with httpx.Client() as c:
        esr = EsrClient(c, cfg, FAKE_KEY)
        now = datetime(2026, 11, 9, tzinfo=UTC)
        check = spec.check_bundle  # type: ignore[attr-defined]
        if country == 5700:
            res = esr_ingest.ingest(esr, store, now, check=check)
            assert res.ingested == ["2026-11-05"]
            return
        with pytest.raises(EsrError, match="99999"):
            esr_ingest.ingest(esr, store, now, check=check)
    assert set(manifest.releases("export_sales")) == {"2026-10-29"}
    assert sorted(p.name for p in (tmp_path / "export_sales").iterdir()) == ["2026-10-29.json.gz"]


def test_bundle_bytes_are_deterministic(bundle):
    a = encode_bundle(bundle)
    b = encode_bundle(json.loads(json.dumps(bundle)))
    assert a == b and decode_bundle(a) == bundle


# ── silver ──────────────────────────────────────────────────────────────────


def _snap(bundle: dict, seq: int, key: str, kind: str = "backfill") -> Snapshot:
    b = copy.deepcopy(bundle)
    b["kind"] = kind
    b["release_key"] = key
    return Snapshot(key=key, seq=seq, sha256=f"{seq:064d}", edition=1, bundle=b)


def test_silver_frame_envelope_and_release_dating(cfg, bundle, parse_ctx):
    df = build_frame(
        [_snap(bundle, 1, "2025-09-11")],
        cfg,
        parse_ctx["countries"],
        parse_ctx["starts"],
        parse_ctx["calendar"],
    )
    assert list(df.columns[:7]) == [
        "report_id",
        "release_key",
        "release_ts_utc",
        "edition",
        "source",
        "bronze_sha256",
        "vintage_quality",
    ]
    assert set(df.vintage_quality) == {"latest_only"}
    assert set(df.unit_id) == {"mt"} and set(df.region_id) == {"united_states"}
    newest = df[df.week_ending == date(2025, 9, 4)]
    assert set(newest.release_key) == {"2025-09-11"} and set(newest.release_ts_source) == {"api"}
    assert newest.release_ts_utc.iloc[0] == pd.Timestamp("2025-09-11 12:30", tz="UTC")
    # Labor Day (Mon 2025-09-01) moves that week's release to Friday.
    older = df[df.week_ending == date(2025, 8, 28)]
    assert set(older.release_key) == {"2025-09-05"} and set(older.release_ts_source) == {
        "calendar_rule"
    }
    corn = df[(df.commodity_id == "corn") & (df.esr_market_year == 2025)]
    assert set(corn.market_year) == {"2024/25"} and corn.week_of_my.min() == 1
    china = df[
        (df.commodity_id == "soybeans")
        & (df.country_id == "china")
        & (df.metric == "total_commitment")
    ]
    assert len(china) > 0
    contract = Contract.load(parse_ctx_path("contracts/export_sales.yaml"))
    validate(df, contract, cfg)


def parse_ctx_path(rel: str):
    from usda_reports.core.config import PROJECT_ROOT

    return PROJECT_ROOT / "config" / rel


def test_change_log_keeps_only_changes_and_tombstones(cfg, bundle, parse_ctx):
    first = _snap(bundle, 1, "2025-09-11")
    later = copy.deepcopy(bundle)
    # A week later: soybeans MY 2025 → Japan revised, Mexico dropped for week 2025-09-04.
    soy = next(r for r in later["responses"] if r["commodity_code"] == 801)
    for r in soy["records"]:
        if r["weekEndingDate"].startswith("2025-09-04") and r["countryCode"] == 5880:
            r["accumulatedExports"] += 1000
    soy["records"] = [
        r
        for r in soy["records"]
        if not (r["weekEndingDate"].startswith("2025-09-04") and r["countryCode"] == 2010)
    ]
    second = _snap(later, 2, "2025-09-18", kind="weekly")
    df = build_frame(
        [first, second],
        cfg,
        parse_ctx["countries"],
        parse_ctx["starts"],
        parse_ctx["calendar"],
    )
    s2 = df[df.snapshot_seq == 2]
    assert set(s2.vintage_quality) == {"captured"}
    japan = s2[(s2.country_id == "japan") & (s2.metric == "accumulated_exports")]
    assert len(japan) == 1 and japan.week_ending.iloc[0] == date(2025, 9, 4)
    mexico = s2[s2.country_id == "mexico"]
    assert len(mexico) and (mexico.value == 0).all()  # tombstones
    assert set(s2.commodity_id) == {"soybeans"}  # nothing else changed
    # The latest value per key is the last row: Japan's revision wins.
    last = df.sort_values("snapshot_seq").drop_duplicates(
        ["commodity_id", "esr_market_year", "week_ending", "country_id", "metric"], keep="last"
    )
    j = last[
        (last.commodity_id == "soybeans")
        & (last.country_id == "japan")
        & (last.metric == "accumulated_exports")
        & (last.week_ending == date(2025, 9, 4))
    ]
    assert j.snapshot_seq.iloc[0] == 2


def test_unseen_country_and_wrong_unit_fail(cfg, bundle, parse_ctx):
    bad = copy.deepcopy(bundle)
    bad["responses"][0]["records"][0]["countryCode"] = 12345
    with pytest.raises(UnseenLabelError, match="12345"):
        build_frame(
            [_snap(bad, 1, "2025-09-11")],
            cfg,
            parse_ctx["countries"],
            parse_ctx["starts"],
            parse_ctx["calendar"],
        )
    bales = copy.deepcopy(bundle)
    bales["responses"][0]["records"][0]["unitId"] = 2
    with pytest.raises(EsrError, match="unitId"):
        build_frame(
            [_snap(bales, 1, "2025-09-11")],
            cfg,
            parse_ctx["countries"],
            parse_ctx["starts"],
            parse_ctx["calendar"],
        )


def test_newest_release_must_cover_every_commodity(cfg, bundle, parse_ctx):
    partial = copy.deepcopy(bundle)
    partial["responses"] = [r for r in partial["responses"] if r["commodity_code"] != 902]
    df = build_frame(
        [_snap(partial, 1, "2025-09-11")],
        cfg,
        parse_ctx["countries"],
        parse_ctx["starts"],
        parse_ctx["calendar"],
    )
    with pytest.raises(ContractError, match="soybean_oil"):
        validate(df, Contract.load(parse_ctx_path("contracts/export_sales.yaml")), cfg)


def test_spec_reads_key_from_settings(config_dir, monkeypatch):
    from usda_reports.core.registry import load_registry

    monkeypatch.delenv("FAS_API_KEY", raising=False)
    monkeypatch.setenv("USDA_PSD_KEY", FAKE_KEY)
    s = Settings(_env_file=None, config_dir=config_dir)
    spec = load_registry(config_dir).spec("export_sales", s)
    with httpx.Client() as c:
        esr = spec.esr_client(c)  # type: ignore[attr-defined]
    assert esr.api_key == FAKE_KEY
    assert FAKE_KEY not in repr(esr)
