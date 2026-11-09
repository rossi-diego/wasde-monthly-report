"""USDA OCE machine-readable WASDE CSV (available from 2021-01)."""

from __future__ import annotations

import httpx

from wasde.config import get_settings
from wasde.logs import get_logger
from wasde.net import get

log = get_logger(__name__)

CSV_FIRST_MONTH = "2021-01"
CSV_HEADER_PREFIX = b"WasdeNumber"


class NotACsvError(ValueError):
    """The response body is not a WASDE CSV (e.g. an HTML error page)."""


def csv_url(report_month: str) -> str:
    year, month = (int(p) for p in report_month.split("-"))
    return get_settings().usda_csv_url.format(year=year, month=month)


def fetch_csv(client: httpx.Client, report_month: str) -> bytes | None:
    """Download the CSV for ``YYYY-MM``. ``None`` when not published (404)."""
    url = csv_url(report_month)
    resp = get(client, url)
    if resp is None:
        log.info("usda_csv.not_found", month=report_month)
        return None
    body = resp.content.lstrip(b"\xef\xbb\xbf")
    if not body.lstrip(b'"').startswith(CSV_HEADER_PREFIX):  # header is quoted in some months
        raise NotACsvError(f"{url} did not return a WASDE CSV (got {body[:60]!r})")
    return body
