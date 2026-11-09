"""Manifest v2 and the lossless v1 migration, tested on the real committed v1 manifest."""

import json

import pytest

from usda_reports.core.manifest import SCHEMA_VERSION, Manifest, migrate_v1, release_ts_utc


@pytest.fixture
def v1(fixtures) -> dict:
    return json.loads((fixtures / "manifest_v1.json").read_text(encoding="utf-8"))


def test_migrate_v1_keeps_every_release(v1):
    v2 = migrate_v1(v1)
    assert v2["schema_version"] == SCHEMA_VERSION == 2
    assert v2["data_release_tag"] == v1["data_release_tag"] == "data-2026-10"
    wasde = v2["reports"]["wasde"]
    assert wasde["latest_release_key"] == v1["latest_report"]
    assert wasde["latest_number"] == v1["latest_wasde_number"]
    assert wasde["total_rows"] == v1["total_rows"]
    assert set(wasde["releases"]) == set(v1["reports"])
    assert len(wasde["releases"]) == 193
    for key, old in v1["reports"].items():
        new = wasde["releases"][key]
        for field in ("source", "file", "url", "sha256", "bytes", "release_date", "fetched_at"):
            assert new[field] == old[field], (key, field)
        assert new["edition"] == old["version"]
        assert new["status"] == "ok" and new["shard"] is None


def test_migrate_v1_derives_release_instant_in_et(v1):
    rel = migrate_v1(v1)["reports"]["wasde"]["releases"]
    assert rel["2010-07"]["release_ts_utc"] == "2010-07-09T16:00:00+00:00"  # EDT
    assert rel["2010-12"]["release_ts_utc"] == "2010-12-10T17:00:00+00:00"  # EST
    assert rel["2026-10"]["release_ts_utc"] is None  # CSV entry without a release date


def test_load_upgrades_v1_and_save_writes_v2(fixtures, tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes((fixtures / "manifest_v1.json").read_bytes())
    m = Manifest.load(path)
    assert m.schema_version == 2 and len(m.releases("wasde")) == 193
    m.save(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2 and "wasde" in raw["reports"]
    again = Manifest.load(path)
    assert again.model_dump(exclude={"updated_at"}) == m.model_dump(exclude={"updated_at"})


def test_summary_and_ok_skip_skipped_releases():
    m = Manifest()
    m.releases("wasde")["2013-09"] = m.releases("wasde").get("x") or _entry()
    m.releases("wasde")["2013-10"] = _entry(status="skipped")
    assert list(m.report("wasde").ok()) == ["2013-09"]
    assert m.summary()["wasde"] == {"releases": 1, "first": "2013-09", "latest": "2013-09"}


def test_release_ts_utc_rejects_garbage():
    assert release_ts_utc("not-a-date") is None
    assert release_ts_utc("2026-11-06", "08:30") == "2026-11-06T13:30:00+00:00"


def _entry(status: str = "ok"):
    from usda_reports.core.manifest import ReleaseEntry

    return ReleaseEntry(source="esmis_xml", file="esmis_xml/x.xml", sha256="0", status=status)
