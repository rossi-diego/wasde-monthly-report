"""Download a NASS release zip (URL from ESMIS ``files[]``) and read members from it.

The zip is stored in bronze byte-for-byte; parsing always reads from the stored bytes. A body
that is not a zip (an HTML error page behind a 200, a truncated download) is rejected before
anything reaches bronze.
"""

from __future__ import annotations

import io
import zipfile
from fnmatch import fnmatch

import httpx

from usda_reports.core.net import get


class NassZipError(RuntimeError):
    """The downloaded file is not a usable NASS release zip."""


def is_zip(data: bytes) -> bool:
    if not data.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return zf.testzip() is None
    except zipfile.BadZipFile:
        return False


def fetch_zip(client: httpx.Client, url: str) -> bytes | None:
    """The zip at ``url``; None on 404. Raises :class:`NassZipError` on a non-zip body."""
    resp = get(client, url)
    if resp is None:
        return None
    if not is_zip(resp.content):
        raise NassZipError(f"{url}: not a zip ({len(resp.content)} bytes)")
    return resp.content


def members(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.namelist()


def read_member(data: bytes, pattern: str) -> tuple[str, bytes]:
    """(name, bytes) of the single member matching the glob ``pattern`` (case-insensitive)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            hits = [n for n in zf.namelist() if fnmatch(n.lower(), pattern.lower())]
            if len(hits) != 1:
                raise NassZipError(f"expected one member matching {pattern!r}, found {hits}")
            return hits[0], zf.read(hits[0])
    except zipfile.BadZipFile as exc:
        raise NassZipError(f"not a zip: {exc}") from exc
