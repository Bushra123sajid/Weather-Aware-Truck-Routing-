"""Application error types rendered by :mod:`apps.common.exceptions`."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base error with an HTTP status and a stable machine-readable code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderError(AppError):
    """An upstream API (routing, geocoding, weather) failed or returned junk."""

    status_code = 502
    code = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        upstream_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {"provider": provider, **(details or {})}
        if upstream_status is not None:
            merged["upstream_status"] = upstream_status
        super().__init__(message, details=merged)
        self.provider = provider
        self.upstream_status = upstream_status


class NoRouteError(AppError):
    status_code = 422
    code = "no_route"


class LocationNotFoundError(AppError):
    status_code = 422
    code = "location_not_found"


class PlanExpiredError(AppError):
    status_code = 404
    code = "plan_expired"
