"""Shared HTTP client with timeouts, retries and exponential backoff."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .errors import ProviderError

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "routewise/1.0"


def build_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    """Create a session that retries idempotent failures (429/5xx, connect errors)."""
    retry = Retry(
        total=settings.HTTP_RETRIES,
        connect=settings.HTTP_RETRIES,
        read=settings.HTTP_RETRIES,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    provider: str,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    """Perform a request and return decoded JSON, raising :class:`ProviderError` on failure."""
    try:
        resp = session.request(
            method, url, timeout=timeout or settings.HTTP_TIMEOUT_SECONDS, **kwargs
        )
    except requests.RequestException as exc:
        logger.warning("%s request failed: %s", provider, exc)
        raise ProviderError(f"{provider} is unreachable", provider=provider) from exc

    if resp.status_code >= 400:
        body = resp.text[:500]
        logger.warning("%s returned %s: %s", provider, resp.status_code, body)
        raise ProviderError(
            f"{provider} returned HTTP {resp.status_code}",
            provider=provider,
            upstream_status=resp.status_code,
            details={"body": body},
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(f"{provider} returned invalid JSON", provider=provider) from exc
