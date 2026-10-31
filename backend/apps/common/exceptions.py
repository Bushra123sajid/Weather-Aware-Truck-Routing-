"""DRF exception handler that renders every error as {"error": {"code", "message", "details"}}."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .errors import AppError

logger = logging.getLogger(__name__)


def _first_message(detail: Any) -> str:
    if isinstance(detail, dict):
        for key, value in detail.items():
            msg = _first_message(value)
            return msg if key == "non_field_errors" else f"{key}: {msg}"
    if isinstance(detail, list) and detail:
        return _first_message(detail[0])
    return str(detail)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, AppError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status=exc.status_code,
        )

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Internal server error", "details": {}}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        code, message, details = "validation_error", _first_message(exc.detail), exc.detail
    elif isinstance(exc, exceptions.Throttled):
        code, message, details = "throttled", str(exc.detail), {"wait": exc.wait}
    else:
        code = getattr(exc, "default_code", "error")
        message = _first_message(getattr(exc, "detail", str(exc)))
        details = {}
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
