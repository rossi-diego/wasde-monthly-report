"""Append-only bronze delta shards for the long-lived ``bronze-store`` GitHub prerelease.

Runners are ephemeral, so bronze is persisted as tarballs:

* ``bronze__<report_id>__base.tar.gz``     every file of the first pack (the backfill);
* ``bronze__<report_id>__<YYYY-MM>.tar.gz`` only the files added or changed that month
  (``.2``, ``.3``… are appended when the same month is packed again).

The manifest records, per release, the shard that holds its bytes. Shards are never deleted
or rewritten once a published manifest references them, so any immutable ``data-*`` release
can be rebuilt from its own manifest. Unpacking extracts each file from the shard its
manifest entry names (a re-ingested edition lives in a newer shard than the original) and
verifies the sha256.
"""

from __future__ import annotations

import io
import re
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from usda_reports.bronze.store import file_sha256
from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest

log = get_logger(__name__)

STORE_TAG = "bronze-store"
_SHARD_RE = re.compile(
    r"^bronze__(?P<report>[a-z0-9_]+)__(?P<period>base|\d{4}-\d{2})(?:\.(?P<n>\d+))?\.tar\.gz$"
)


class ShardError(RuntimeError):
    pass


def shard_name(report_id: str, period: str = "base", n: int = 1) -> str:
    suffix = f".{n}" if n > 1 else ""
    return f"bronze__{report_id}__{period}{suffix}.tar.gz"


def parse_shard_name(name: str) -> tuple[str, str, int]:
    m = _SHARD_RE.match(name)
    if not m:
        raise ShardError(f"not a bronze shard name: {name!r}")
    return m["report"], m["period"], int(m["n"] or 1)


def next_shard_name(manifest: Manifest, report_id: str, now: datetime | None = None) -> str:
    """Base shard for a report's first pack, then one shard per UTC month (deduplicated)."""
    used = set(manifest.report(report_id).shards_written) | manifest.shards(report_id)
    if not used:
        return shard_name(report_id)
    period = f"{(now or datetime.now(UTC)):%Y-%m}"
    n = 1
    while shard_name(report_id, period, n) in used:
        n += 1
    return shard_name(report_id, period, n)


def pending(manifest: Manifest, report_id: str) -> list[str]:
    """Release keys whose bronze file is not in any shard yet."""
    return [k for k, e in manifest.report(report_id).ok().items() if e.shard is None]


def _add_file(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    """Add with fixed metadata so the tarball content does not depend on the runner."""
    info = tarfile.TarInfo(arcname)
    data = path.read_bytes()
    info.size = len(data)
    info.mtime = 0
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


def pack_shards(
    bronze_root: Path, manifest: Manifest, out_dir: Path, now: datetime | None = None
) -> list[Path]:
    """Pack every not-yet-sharded bronze file into one new shard per report.

    Updates ``manifest`` in place (``entry.shard``); the caller saves it. Returns the shard
    files written (empty when nothing is pending).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for report_id in sorted(manifest.reports):
        keys = pending(manifest, report_id)
        if not keys:
            continue
        name = next_shard_name(manifest, report_id, now)
        out = out_dir / name
        releases = manifest.releases(report_id)
        with tarfile.open(out, "w:gz", compresslevel=6) as tar:
            for key in keys:
                e = releases[key]
                assert e.file is not None
                src = bronze_root / e.file
                if not src.exists() or file_sha256(src) != e.sha256:
                    raise ShardError(f"{report_id}/{key}: bronze file missing or hash mismatch")
                _add_file(tar, src, e.file)
        for key in keys:
            releases[key].shard = name
        manifest.report(report_id).shards_written.append(name)
        log.info("bronze.shard_packed", report=report_id, shard=name, files=len(keys))
        written.append(out)
    return written


def required_shards(manifest: Manifest) -> list[str]:
    """Shards needed to restore every bronze file of the manifest."""
    return sorted(manifest.shards())


def unpack_shards(shard_dir: Path, bronze_root: Path, manifest: Manifest) -> int:
    """Restore each manifest file from the shard it is recorded in, verifying sha256.

    Returns the number of files restored. Raises :class:`ShardError` when a shard or a
    member is missing, when a hash does not match, or when entries have no shard at all.
    """
    by_shard: dict[str, dict[str, str]] = {}
    unsharded = []
    for report_id, state in manifest.reports.items():
        for key, e in state.ok().items():
            if e.shard is None:
                unsharded.append(f"{report_id}/{key}")
                continue
            assert e.file is not None and e.sha256 is not None
            by_shard.setdefault(e.shard, {})[e.file] = e.sha256
    if unsharded:
        raise ShardError(f"manifest entries without a shard: {unsharded[:5]}…")
    restored = 0
    for name, members in sorted(by_shard.items()):
        path = shard_dir / name
        if not path.exists():
            raise ShardError(f"shard {name} not found in {shard_dir}")
        with tarfile.open(path, "r:gz") as tar:
            names = set(tar.getnames())
            for arc, sha in sorted(members.items()):
                if arc not in names:
                    raise ShardError(f"{arc} missing from shard {name}")
                tar.extract(arc, bronze_root, filter="data")
                if file_sha256(bronze_root / arc) != sha:
                    raise ShardError(f"{arc} from {name}: sha256 mismatch")
                restored += 1
    log.info("bronze.shards_unpacked", shards=len(by_shard), files=restored)
    return restored
