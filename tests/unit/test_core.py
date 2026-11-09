"""Settings (USDA_ prefix + WASDE_ fallback), registry, contracts, vocab and dbt seeds."""

import csv

import pandas as pd
import pytest

from usda_reports.core.config import PROJECT_ROOT, Settings, apply_legacy_env
from usda_reports.core.contracts import ContractError
from usda_reports.core.registry import load_registry
from usda_reports.core.vocab import UnseenLabelError, Vocab
from usda_reports.reports.export_sales.spec import ExportSalesSpec
from usda_reports.reports.wasde.silver import load_contract
from usda_reports.reports.wasde.spec import WasdeSpec
from usda_reports.silver.envelope import ENVELOPE_COLUMNS, add_envelope

SEEDS = PROJECT_ROOT / "dbt" / "seeds"


# ── settings ────────────────────────────────────────────────────────────────


def test_legacy_wasde_prefix_is_mapped_once(tmp_path):
    env = {"WASDE_LOG_LEVEL": "DEBUG", "WASDE_DATA_DIR": "old", "USDA_DATA_DIR": "new"}
    used = apply_legacy_env(env, dotenv=tmp_path / "missing.env")
    assert used == ["WASDE_LOG_LEVEL"]  # USDA_DATA_DIR wins, so WASDE_DATA_DIR is ignored
    assert env["USDA_LOG_LEVEL"] == "DEBUG" and env["USDA_DATA_DIR"] == "new"


def test_legacy_prefix_read_from_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nWASDE_LOG_JSON=true\n", encoding="utf-8")
    env: dict[str, str] = {}
    assert apply_legacy_env(env, dotenv=dotenv) == ["WASDE_LOG_JSON"]
    assert env == {"USDA_LOG_JSON": "true"}


def test_usda_prefix_and_fas_key_fallback(monkeypatch):
    monkeypatch.setenv("USDA_LOG_LEVEL", "WARNING")
    monkeypatch.delenv("FAS_API_KEY", raising=False)
    monkeypatch.setenv("USDA_PSD_KEY", "psd-secret")
    s = Settings(_env_file=None)
    assert s.log_level == "WARNING"
    assert s.fas_api_key is not None and s.fas_api_key.get_secret_value() == "psd-secret"
    assert "psd-secret" not in repr(s)  # never printed
    monkeypatch.setenv("FAS_API_KEY", "fas-secret")
    assert Settings(_env_file=None).fas_api_key.get_secret_value() == "fas-secret"


# ── registry / spec ─────────────────────────────────────────────────────────


def test_registry_enables_wasde_and_export_sales(config_dir):
    reg = load_registry(config_dir)
    assert [r.id for r in reg.enabled()] == ["wasde", "export_sales"]
    assert {"export_sales", "oilseed_crush", "crop_progress", "grain_stocks"} <= set(reg.reports)
    spec = reg.spec("wasde", Settings(config_dir=config_dir))
    assert isinstance(spec, WasdeSpec)
    assert spec.config_dir == config_dir / "reports" / "wasde"
    assert (spec.config_dir / "focus.yaml").exists()
    assert (spec.config_dir / "mappings.yaml").exists()
    assert (spec.config_dir / "xml_layout" / "positions.csv").exists()
    assert spec.calendar(), "config/calendars/wasde.yaml has release dates"
    esr = reg.spec("export_sales", Settings(config_dir=config_dir))
    assert isinstance(esr, ExportSalesSpec)
    assert esr.config.release_time_et == "08:30" and esr.config.cadence == "weekly"
    with pytest.raises(ValueError, match="no spec"):
        reg.spec("oilseed_crush", Settings(config_dir=config_dir))


# ── envelope + contract ─────────────────────────────────────────────────────


def _silver_rows(core_series):
    return pd.DataFrame(
        [
            {
                "report_month": "2024-05",
                "source": "usda_csv",
                "table_id": t,
                "commodity_id": c,
                "region_id": r,
                "attribute_id": a,
                "market_year": "2024/25",
                "period": "annual",
                "reliability_stat": "",
                "value": 1.0,
            }
            for t, c, r, a in core_series
        ]
    )


def test_envelope_is_added_and_checked(config_dir):
    from usda_reports.core.manifest import ReleaseEntry

    contract = load_contract(config_dir)
    df = _silver_rows(contract.required_per_release.tuples())
    releases = {
        "2024-05": ReleaseEntry(
            source="usda_csv", sha256="ab" * 32, release_ts_utc="2024-05-10T16:00:00+00:00"
        )
    }
    silver = add_envelope(df, "wasde", "report_month", releases)
    assert list(silver.columns[: len(ENVELOPE_COLUMNS)]) == ENVELOPE_COLUMNS
    assert set(df.columns) <= set(silver.columns)  # nothing dropped
    assert silver["release_key"].eq("2024-05").all() and silver["edition"].eq(1).all()
    contract.enforce(silver, min_rows=1)

    broken = silver.assign(vintage_quality="guess")
    with pytest.raises(ContractError, match="vintage_quality"):
        contract.enforce(broken, min_rows=1)
    with pytest.raises(ContractError, match="missing envelope"):
        contract.enforce(df, min_rows=1, envelope=True)


# ── vocab + seeds ───────────────────────────────────────────────────────────


def test_vocab_resolves_aliases_and_fails_on_unseen(config_dir):
    v = Vocab.load(config_dir / "vocab" / "commodities.yaml")
    assert v.resolve("SOYBEANS") == "soybeans" and v.resolve("soybean meal") == "soybean_meal"
    with pytest.raises(UnseenLabelError):
        v.resolve("Sunflowerseed")
    assert v.unseen(["Corn", "Canola"]) == ["Canola"]


def _rows(name: str) -> list[dict[str, str]]:
    with (SEEDS / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_dim_unit_round_trip_every_row():
    rows = _rows("dim_unit.csv")
    assert len({(r["unit_id"], r["commodity_id"]) for r in rows}) == len(rows)
    for r in rows:
        to_mt, from_mt = float(r["to_mt"]), float(r["from_mt"])
        assert to_mt * from_mt == pytest.approx(1.0, rel=1e-9), r["unit_id"]
        native = 123.456
        assert native * to_mt * from_mt == pytest.approx(native, rel=1e-9)
    by = {(r["unit_id"], r["commodity_id"]): r for r in rows}
    assert float(by[("bu", "corn")]["from_mt"]) == 39.3679
    assert float(by[("bu", "soybeans")]["from_mt"]) == float(by[("bu", "wheat")]["from_mt"])
    assert float(by[("k_short_tons", "")]["to_mt"]) == 907.185  # WASDE soybean meal
    assert float(by[("m_lbs", "")]["to_mt"]) == 453.592  # WASDE soybean oil
    crush = by[("short_ton", "soybeans")]
    bu_soy = float(by[("bu", "soybeans")]["to_mt"])
    assert float(crush["to_mt"]) / float(crush["bu_per_unit"]) == pytest.approx(bu_soy, rel=1e-4)


def test_dim_commodity_matches_vocab_and_my_start(config_dir):
    rows = {r["commodity_id"]: r for r in _rows("dim_commodity.csv")}
    vocab = Vocab.load(config_dir / "vocab" / "commodities.yaml")
    assert set(rows) == vocab.ids()
    assert {k: int(r["my_start_month"]) for k, r in rows.items()} == {
        "corn": 9,
        "soybeans": 9,
        "wheat": 6,
        "soybean_meal": 10,
        "soybean_oil": 10,
        "cotton": 8,
    }
    for r in rows.values():
        assert vocab.resolve(r["wasde_label"]) == r["commodity_id"]
