"""Structured exception hierarchy following RFC 7807 Problem Details.

All ShieldOps domain exceptions extend ``ShieldOpsError`` and are
automatically converted to RFC 7807 JSON responses by the FastAPI
exception handler registered in ``app.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class ShieldOpsError(Exception):
    """Base exception for all ShieldOps domain errors."""

    status_code: int = 500
    error_type: str = "about:blank"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str = "",
        *,
        instance: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.title
        self.instance = instance
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_problem_detail(self) -> dict[str, Any]:
        """RFC 7807 Problem Details JSON object."""
        body: dict[str, Any] = {
            "type": self.error_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
        }
        if self.instance:
            body["instance"] = self.instance
        if self.extra:
            body.update(self.extra)
        return body


class NotFoundError(ShieldOpsError):
    status_code = 404
    error_type = "urn:shieldops:error:not-found"
    title = "Not Found"


class ConflictError(ShieldOpsError):
    status_code = 409
    error_type = "urn:shieldops:error:conflict"
    title = "Conflict"


class ValidationError(ShieldOpsError):
    status_code = 422
    error_type = "urn:shieldops:error:validation"
    title = "Validation Error"


class PolicyDeniedError(ShieldOpsError):
    status_code = 403
    error_type = "urn:shieldops:error:policy-denied"
    title = "Policy Denied"


class RateLimitError(ShieldOpsError):
    status_code = 429
    error_type = "urn:shieldops:error:rate-limit"
    title = "Rate Limit Exceeded"


class CircuitOpenError(ShieldOpsError):
    status_code = 503
    error_type = "urn:shieldops:error:circuit-open"
    title = "Circuit Open"


class ExternalServiceError(ShieldOpsError):
    status_code = 502
    error_type = "urn:shieldops:error:external-service"
    title = "External Service Error"


class AuthenticationError(ShieldOpsError):
    status_code = 401
    error_type = "urn:shieldops:error:authentication"
    title = "Authentication Required"


@contextmanager
def error_context(
    error_cls: type[ShieldOpsError] = ShieldOpsError,
    detail: str = "",
    **kwargs: Any,
) -> Iterator[None]:
    """Context manager that wraps unexpected exceptions into structured errors.

    Usage::

        with error_context(ExternalServiceError, detail="OPA call failed"):
            result = await opa_client.evaluate(...)
    """
    try:
        yield
    except ShieldOpsError:
        raise
    except Exception as exc:
        msg = detail or str(exc)
        raise error_cls(msg, **kwargs) from exc


def shieldops_exception_handler(_request: Request, exc: ShieldOpsError) -> JSONResponse:
    """FastAPI exception handler for ShieldOpsError subclasses."""
    logger.warning(
        "shieldops_error",
        error_type=exc.error_type,
        status=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_problem_detail(),
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all ShieldOps exception handlers on the FastAPI app."""
    app.add_exception_handler(ShieldOpsError, shieldops_exception_handler)  # type: ignore[arg-type]
