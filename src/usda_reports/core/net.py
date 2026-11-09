"""Shared HTTP client: browser user agent, retries, and HTML-instead-of-data detection."""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from usda_reports.core.config import get_settings
from usda_reports.core.logs import get_logger

log = get_logger(__name__)


class SourceBlockedError(RuntimeError):
    """The source answered with an access-denied page (Akamai 403) instead of data."""


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, httpx.TransportError)


def make_client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(
        headers={
            "User-Agent": s.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/csv,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        timeout=s.http_timeout_s,
    )


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def get(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET ``url``. Returns ``None`` on 404; raises on blocks and other errors."""
    resp = client.get(url)
    if resp.status_code == 404:
        return None
    if resp.status_code == 403:
        raise SourceBlockedError(f"403 Access Denied from {url}")
    resp.raise_for_status()
    return resp
