"""bronze-store delta shards: naming, append-only packing and verified restore."""

import tarfile
from datetime import UTC, datetime

import pytest

from usda_reports.bronze.shards import (
    ShardError,
    next_shard_name,
    pack_shards,
    parse_shard_name,
    required_shards,
    unpack_shards,
)
from usda_reports.bronze.store import BronzeStore
from usda_reports.core.manifest import Manifest

NOV = datetime(2026, 11, 10, 18, tzinfo=UTC)


def _store(tmp_path) -> BronzeStore:
    return BronzeStore(tmp_path / "bronze", Manifest())


def test_first_pack_is_base_then_monthly_deltas(tmp_path):
    store = _store(tmp_path)
    store.put("2026-09", b"sep", source="usda_csv", url="u")
    store.put("2026-10", b"oct", source="usda_csv", url="u")
    out = tmp_path / "shards"
    [base] = pack_shards(store.root, store.manifest, out, now=NOV)
    assert base.name == "bronze__wasde__base.tar.gz"
    assert pack_shards(store.root, store.manifest, out, now=NOV) == []  # nothing pending

    store.put("2026-11", b"nov", source="usda_csv", url="u")
    [delta] = pack_shards(store.root, store.manifest, out, now=NOV)
    assert delta.name == "bronze__wasde__2026-11.tar.gz"
    with tarfile.open(delta) as tar:
        assert tar.getnames() == ["usda_csv/2026-11.csv"]  # only the new file

    store.put("2026-11", b"nov v2", source="usda_csv", url="u", edition=2)  # revised edition
    [again] = pack_shards(store.root, store.manifest, out, now=NOV)
    assert again.name == "bronze__wasde__2026-11.2.tar.gz"
    assert required_shards(store.manifest) == [
        "bronze__wasde__2026-11.2.tar.gz",
        "bronze__wasde__base.tar.gz",
    ]
    assert parse_shard_name(again.name) == ("wasde", "2026-11", 2)


def test_unpack_restores_each_file_from_its_recorded_shard(tmp_path):
    store = _store(tmp_path)
    store.put("2026-10", b"oct", source="usda_csv", url="u")
    store.put("2026-11", b"nov v1", source="usda_csv", url="u")
    out = tmp_path / "shards"
    pack_shards(store.root, store.manifest, out, now=NOV)
    store.put("2026-11", b"nov v2", source="usda_csv", url="u", edition=2)
    pack_shards(store.root, store.manifest, out, now=NOV)

    fresh = tmp_path / "restored"
    n = unpack_shards(out, fresh, store.manifest)
    assert n == 2
    assert (fresh / "usda_csv" / "2026-11.csv").read_bytes() == b"nov v2"  # not the base copy
    assert BronzeStore(fresh, store.manifest).verify() == []


def test_unpack_fails_loudly(tmp_path):
    store = _store(tmp_path)
    store.put("2026-10", b"oct", source="usda_csv", url="u")
    with pytest.raises(ShardError, match="without a shard"):
        unpack_shards(tmp_path / "none", tmp_path / "r", store.manifest)
    out = tmp_path / "shards"
    pack_shards(store.root, store.manifest, out, now=NOV)
    with pytest.raises(ShardError, match="not found"):
        unpack_shards(tmp_path / "elsewhere", tmp_path / "r", store.manifest)
    store.entries["2026-10"].sha256 = "0" * 64
    with pytest.raises(ShardError, match="sha256 mismatch"):
        unpack_shards(out, tmp_path / "r", store.manifest)


def test_pack_refuses_corrupt_bronze(tmp_path):
    store = _store(tmp_path)
    store.put("2026-10", b"oct", source="usda_csv", url="u")
    (store.root / "usda_csv" / "2026-10.csv").write_bytes(b"tampered")
    with pytest.raises(ShardError, match="hash mismatch"):
        pack_shards(store.root, store.manifest, tmp_path / "s", now=NOV)


def test_next_name_and_bad_names():
    m = Manifest()
    assert next_shard_name(m, "wasde", NOV) == "bronze__wasde__base.tar.gz"
    with pytest.raises(ShardError):
        parse_shard_name("bronze.tar.gz")
