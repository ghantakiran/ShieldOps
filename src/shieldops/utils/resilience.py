"""Circuit breaker and retry-with-backoff resilience primitives.

Provides:
- CircuitBreaker: Three-state (CLOSED/OPEN/HALF_OPEN) breaker for external calls.
- retry_with_backoff: Async decorator with exponential backoff + jitter.
- CircuitOpenError: Raised when the breaker is open.

These are zero-dependency (no external libs), async-native, and use
time.monotonic() for timing to avoid clock-skew issues.
"""

import asyncio
import functools
import random
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────────
# Circuit Breaker
# ────────────────────────────────────────────────────────────────────


class CircuitState(StrEnum):
    """Possible states of the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and rejecting calls."""

    def __init__(self, name: str, recovery_in: float) -> None:
        self.name = name
        self.recovery_in = recovery_in
        super().__init__(f"Circuit breaker '{name}' is open. Recovery in {recovery_in:.1f}s.")


class CircuitBreaker:
    """Three-state circuit breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

    CLOSED:    Requests pass through normally; failures are counted.
               When consecutive failures >= failure_threshold the
               breaker trips to OPEN.
    OPEN:      All calls immediately raise CircuitOpenError.
               After recovery_timeout seconds the breaker moves to
               HALF_OPEN.
    HALF_OPEN: Up to half_open_max_calls probe requests are allowed
               through. A single success resets to CLOSED; a single
               failure trips back to OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._half_open_calls: int = 0
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    # ── Public properties ──────────────────────────────────────────

    @property
    def state(self) -> str:
        """Return current state, auto-transitioning OPEN -> HALF_OPEN
        when the recovery timeout has elapsed."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state.value

    @property
    def stats(self) -> dict[str, Any]:
        """Return a snapshot of breaker counters."""
        return {
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
        }

    # ── Core call method ───────────────────────────────────────────

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute *func* through the circuit breaker.

        Args:
            func: An async callable to invoke.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*.

        Raises:
            CircuitOpenError: When the breaker is in the OPEN state.
        """
        # Refresh state (may auto-transition OPEN -> HALF_OPEN)
        current = self.state

        if current == CircuitState.OPEN:
            recovery_in = self._recovery_timeout - (time.monotonic() - self._opened_at)
            raise CircuitOpenError(self._name, max(recovery_in, 0.0))

        if current == CircuitState.HALF_OPEN and self._half_open_calls >= self._half_open_max_calls:
            recovery_in = self._recovery_timeout
            raise CircuitOpenError(self._name, recovery_in)

        if current == CircuitState.HALF_OPEN:
            self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
        except Exception:
            self._record_failure()
            raise

        self._record_success()
        return result

    # ── Manual reset ───────────────────────────────────────────────

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED state."""
        self._transition(CircuitState.CLOSED)
        self._failure_count = 0
        self._half_open_calls = 0

    # ── Internal helpers ───────────────────────────────────────────

    def _record_success(self) -> None:
        self._success_count += 1
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            # Reset consecutive failure count on success
            self._failure_count = 0

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED and self._failure_count >= self._failure_threshold:
            self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        if old == new_state:
            return
        self._state = new_state
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        logger.info(
            "circuit_breaker_state_change",
            name=self._name,
            old_state=old.value,
            new_state=new_state.value,
        )


# ────────────────────────────────────────────────────────────────────
# Retry with backoff decorator
# ────────────────────────────────────────────────────────────────────


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., Any]:
    """Decorator for async functions with exponential backoff + jitter.

    Args:
        max_retries: Maximum number of retry attempts (excludes the
            initial call).
        base_delay: Starting delay in seconds.
        max_delay: Upper bound on delay in seconds.
        exponential_base: Multiplier base for exponential growth.
        jitter: When True, multiply the delay by a random factor in
            [0.5, 1.5] to decorrelate retries.
        retryable_exceptions: Tuple of exception types that trigger a
            retry.  Any exception **not** in this tuple is raised
            immediately.

    Returns:
        Decorated async function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        logger.warning(
                            "retry_exhausted",
                            function=func.__qualname__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(exc),
                        )
                        raise

                    delay = min(
                        base_delay * (exponential_base**attempt),
                        max_delay,
                    )
                    if jitter:
                        delay *= random.uniform(0.5, 1.5)  # noqa: S311

                    logger.info(
                        "retry_attempt",
                        function=func.__qualname__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=round(delay, 3),
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)

            # Unreachable in practice, but satisfies type checkers.
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
