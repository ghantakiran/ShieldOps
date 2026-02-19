"""Graceful shutdown middleware with request draining.

Tracks in-flight requests via an atomic counter and rejects new
requests with 503 Service Unavailable once shutdown has been signaled.
The shutdown procedure waits (with a configurable timeout) for all
in-flight requests to complete before allowing the process to exit.
"""

from __future__ import annotations

import asyncio

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# Paths that must remain reachable during shutdown so that
# orchestrators (Kubernetes, ECS, etc.) can still probe liveness.
_SHUTDOWN_EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})


class ShutdownState:
    """Shared shutdown coordination state.

    A process-wide singleton that tracks whether shutdown has been
    signaled and how many HTTP requests are still being processed.
    """

    def __init__(self) -> None:
        self._shutting_down: bool = False
        self._in_flight: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()
        self._drain_event: asyncio.Event = asyncio.Event()
        # Start signaled so that ``wait_for_drain`` returns
        # immediately when there are no in-flight requests.
        self._drain_event.set()

    # ── Read-only properties ────────────────────────────────────

    @property
    def shutting_down(self) -> bool:
        """Whether shutdown has been signaled."""
        return self._shutting_down

    @property
    def in_flight(self) -> int:
        """Number of requests currently being processed."""
        return self._in_flight

    # ── Mutation helpers ────────────────────────────────────────

    def signal_shutdown(self) -> None:
        """Signal that shutdown has started."""
        self._shutting_down = True
        logger.info(
            "shutdown_state_signaled",
            in_flight=self._in_flight,
        )

    async def increment(self) -> None:
        """Track a new in-flight request."""
        async with self._lock:
            self._in_flight += 1
            # Clear the drain event since there is work in progress.
            self._drain_event.clear()

    async def decrement(self) -> None:
        """Release an in-flight request.

        When the counter drops to zero the drain event is set so that
        ``wait_for_drain`` can return.
        """
        async with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            if self._in_flight == 0:
                self._drain_event.set()

    async def wait_for_drain(self, timeout: float = 30.0) -> bool:
        """Wait until all in-flight requests have completed.

        Returns ``True`` if all requests drained within *timeout*
        seconds, ``False`` if the timeout was reached.
        """
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    def reset(self) -> None:
        """Reset state for testing."""
        self._shutting_down = False
        self._in_flight = 0
        self._drain_event.set()


# ── Singleton accessor ──────────────────────────────────────────────

_shutdown_state: ShutdownState | None = None


def get_shutdown_state() -> ShutdownState:
    """Get or create the singleton ``ShutdownState``."""
    global _shutdown_state  # noqa: PLW0603
    if _shutdown_state is None:
        _shutdown_state = ShutdownState()
    return _shutdown_state


def reset_shutdown_state() -> None:
    """Destroy the singleton (for tests)."""
    global _shutdown_state  # noqa: PLW0603
    _shutdown_state = None


# ── Starlette Middleware ────────────────────────────────────────────


class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """Tracks in-flight requests and rejects new ones during shutdown.

    During normal operation each request increments an atomic counter
    on entry and decrements it on exit (including on error).  Once
    ``ShutdownState.signal_shutdown()`` has been called, new requests
    receive a 503 Service Unavailable response with a ``Retry-After``
    header so that well-behaved clients can retry against another
    instance.

    Liveness probe paths (``/health``) are exempt from rejection so
    that the orchestrator does not mark the pod as dead before it has
    finished draining.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        state = get_shutdown_state()
        path = request.url.path

        if state.shutting_down and path not in _SHUTDOWN_EXEMPT_PATHS:
            logger.debug(
                "request_rejected_during_shutdown",
                path=path,
                method=request.method,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Server is shutting down",
                },
                headers={"Retry-After": "5"},
            )

        await state.increment()
        try:
            response = await call_next(request)
        finally:
            await state.decrement()
        return response
