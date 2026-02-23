"""Circuit breaker pattern for external dependency failure isolation.

Implements the standard CLOSED → OPEN → HALF_OPEN state machine with
configurable failure thresholds, reset timeouts, and half-open call limits.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitStats(BaseModel):
    """Statistics for a circuit breaker."""

    name: str
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    opened_at: float | None = None
    half_open_calls: int = 0
    failure_threshold: int = 5
    reset_timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an open circuit."""

    def __init__(self, name: str, retry_after: float = 0.0) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(f"Circuit '{name}' is OPEN. Retry after {retry_after:.1f}s")


class CircuitBreaker:
    """Circuit breaker for an external dependency.

    Usage::

        breaker = CircuitBreaker("opa", failure_threshold=5, reset_timeout=30.0)
        async with breaker.call():
            result = await call_opa(...)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._last_success_time: float | None = None
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for timeout-based transitions."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.reset_timeout
        ):
            return CircuitState.HALF_OPEN
        return self._state

    @property
    def stats(self) -> CircuitStats:
        return CircuitStats(
            name=self.name,
            state=self.state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_calls=self._total_calls,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
            opened_at=self._opened_at,
            half_open_calls=self._half_open_calls,
            failure_threshold=self.failure_threshold,
            reset_timeout_seconds=self.reset_timeout,
            half_open_max_calls=self.half_open_max_calls,
        )

    @asynccontextmanager
    async def call(self) -> AsyncIterator[None]:
        """Context manager that wraps an external call with circuit breaking."""
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                retry_after = 0.0
                if self._opened_at is not None:
                    elapsed = time.monotonic() - self._opened_at
                    retry_after = max(0.0, self.reset_timeout - elapsed)
                raise CircuitOpenError(self.name, retry_after)

            if current == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(self.name, retry_after=self.reset_timeout)
                self._half_open_calls += 1

            self._total_calls += 1

        try:
            yield
        except Exception:
            await self._record_failure()
            raise
        else:
            await self._record_success()

    async def reset(self) -> None:
        """Force-reset the breaker to CLOSED."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._opened_at = None
            logger.info("circuit_breaker_reset", name=self.name)

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            is_half_open = self.state == CircuitState.HALF_OPEN
            if is_half_open or self._failure_count >= self.failure_threshold:
                self._trip()

    async def _record_success(self) -> None:
        async with self._lock:
            self._success_count += 1
            self._last_success_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                # All half-open calls succeeded → close
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                self._opened_at = None
                logger.info("circuit_breaker_closed", name=self.name)

    def _trip(self) -> None:
        """Transition to OPEN."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_calls = 0
        logger.warning(
            "circuit_breaker_opened",
            name=self.name,
            failures=self._failure_count,
        )


class CircuitBreakerRegistry:
    """Named registry of circuit breakers for all external dependencies."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def register(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """Register (or retrieve) a named circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                reset_timeout=reset_timeout,
                half_open_max_calls=half_open_max_calls,
            )
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        return self._breakers.get(name)

    def all_stats(self) -> list[CircuitStats]:
        return [b.stats for b in self._breakers.values()]

    async def reset(self, name: str) -> bool:
        breaker = self._breakers.get(name)
        if breaker is None:
            return False
        await breaker.reset()
        return True

    async def reset_all(self) -> None:
        for breaker in self._breakers.values():
            await breaker.reset()

    @property
    def names(self) -> list[str]:
        return list(self._breakers.keys())
