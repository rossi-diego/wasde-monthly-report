"""Bronze layer: raw upstream files stored byte-for-byte, plus provenance in the manifest.

Files live at ``data/bronze/<subdir>/<release_key>.<ext>``; WASDE keeps its historical
sub-folders (``usda_csv/``, ``esmis_xml/``) so existing archives and manifests stay valid.
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path

from usda_reports.core.logs import get_logger
from usda_reports.core.manifest import Manifest, ReleaseEntry, release_ts_utc

log = get_logger(__name__)

# Bronze sub-folders per source format (WASDE keeps its historical top-level folders).
SOURCE_DIRS = {
    "usda_csv": ("usda_csv", "csv"),
    "esmis_xml": ("esmis_xml", "xml"),
    "fas_esr_api": ("export_sales", "json.gz"),
}
CSV_DIR = "usda_csv"
XML_DIR = "esmis_xml"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class BronzeStore:
    root: Path
    manifest: Manifest
    report_id: str = "wasde"
    release_time_et: str = "12:00"

    @property
    def entries(self) -> dict[str, ReleaseEntry]:
        """Releases of this store's report, keyed by release_key."""
        return self.manifest.releases(self.report_id)

    def path_for(self, entry: ReleaseEntry) -> Path:
        if entry.file is None:
            raise ValueError("skipped releases have no bronze file")
        return self.root / entry.file

    def put(
        self,
        release_key: str,
        data: bytes,
        *,
        source: str,
        url: str,
        release_date: str | None = None,
        edition: int = 1,
    ) -> ReleaseEntry:
        sub, ext = SOURCE_DIRS.get(source, (f"{self.report_id}/{source}", "bin"))
        rel = f"{sub}/{release_key}.{ext}"
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = ReleaseEntry(
            source=source,
            file=rel,
            url=url,
            sha256=sha256(data),
            bytes=len(data),
            release_date=release_date,
            release_ts_utc=release_ts_utc(release_date, self.release_time_et),
            edition=edition,
            status="ok",
            shard=None,  # new or changed bytes: goes into the next bronze-store shard
        )
        self.entries[release_key] = entry
        log.info(
            "bronze.stored",
            report=self.report_id,
            release_key=release_key,
            source=source,
            bytes=len(data),
        )
        return entry

    def skip(self, release_key: str, source: str, reason: str) -> ReleaseEntry:
        """Record that a scheduled release does not exist (shutdown, cancelled report)."""
        entry = ReleaseEntry(source=source, status="skipped", url=reason)
        self.entries[release_key] = entry
        return entry

    def verify(self) -> list[str]:
        """Return release keys whose file is missing or whose hash no longer matches."""
        bad = []
        for key, e in self.entries.items():
            if e.status != "ok":
                continue
            p = self.path_for(e)
            if not p.exists() or file_sha256(p) != e.sha256:
                bad.append(key)
        return bad


# ── Archive (legacy single-tarball GitHub release asset) ────────────────────


def pack(root: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz", compresslevel=6) as tar:
        for sub in (CSV_DIR, XML_DIR):
            if (root / sub).exists():
                tar.add(root / sub, arcname=sub)
    log.info("bronze.packed", path=str(out), bytes=out.stat().st_size)
    return out


def unpack(archive: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(root, filter="data")
    log.info("bronze.unpacked", path=str(archive))


def reset(root: Path) -> None:
    for sub in (CSV_DIR, XML_DIR):
        shutil.rmtree(root / sub, ignore_errors=True)
