"""Correlation middleware: auto-creates trace + root span per request."""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shieldops.observability.request_correlation import SpanStatus


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Creates a correlation trace and root span for every request.

    Reads the request_id from ``request.state.request_id`` (set by
    ``RequestIDMiddleware``) and auto-creates a trace + root span.
    """

    def __init__(self, app: Any, correlator: Any = None) -> None:
        super().__init__(app)
        self._correlator = correlator

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._correlator is None:
            return await call_next(request)

        state = getattr(request, "state", None)
        request_id = getattr(state, "request_id", None) if state else None
        if not request_id:
            return await call_next(request)

        entry_point = f"{request.method} {request.url.path}"
        self._correlator.start_trace(request_id, entry_point=entry_point)
        span = self._correlator.start_span(request_id, operation=entry_point)

        try:
            response = await call_next(request)
        except Exception:
            if span:
                self._correlator.end_span(request_id, span.span_id, SpanStatus.ERROR)
            self._correlator.end_trace(request_id, SpanStatus.ERROR)
            raise

        status = SpanStatus.COMPLETED if response.status_code < 500 else SpanStatus.ERROR
        if span:
            self._correlator.end_span(
                request_id,
                span.span_id,
                status,
                metadata={"status_code": response.status_code},
            )
        self._correlator.end_trace(request_id, status)

        # Add correlation header
        response.headers["X-Correlation-ID"] = request_id
        return response
